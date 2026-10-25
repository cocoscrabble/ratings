"""Checks on the tournament list and results files: is the corpus well formed?

``check()`` returns a list of problems, each naming the file and line, worded
for whoever is adding a tournament. It is what ``coco-rate check`` prints and
what ``tests/test_corpus.py`` asserts is empty, so a commit that adds a
tournament fails only when something about the files is wrong.

Two levels:

- **Every tournament**: the row in ``data/tournaments.csv`` is well formed and
  has exactly one results file, and every ``.csv``/``.tsv`` in ``results/``
  belongs to a listed tournament (a misnamed file is otherwise silently
  ignored by the replay).
- **Tournaments after the milestone** also get the per-game checks: player
  identity, scores, rounds, duplicates. Frozen files are pinned by sha256 in
  ``milestone/manifest.json`` and their ratings are published, and several
  would fail these checks (a misnumbered round, a winner who scored less);
  fixing one changes its record, which takes a manifest amendment.

Finally the full build is run, which catches anything the reader or the
milestone refuses that the checks above did not anticipate.
"""

from __future__ import annotations

import collections
import csv
import difflib
import re
from datetime import datetime
from pathlib import Path

from coco_ratings import paths
from coco_ratings.identity import canonical_player_number
from coco_ratings.io import ParserError, cell, find_number_columns, normalize_header
from coco_ratings.milestone import Milestone
from coco_ratings.players import PlayerDB
from coco_ratings.tournaments import TournamentEntry
from coco_ratings.types import is_bye

TOURNAMENT_COLUMNS = ["FancyName", "Division", "City", "Name", "Tournament",
                      "Filename", "Date", "Order"]
RESULT_COLUMNS = ["submitted on", "round", "winner", "winners score",
                  "opponent", "opponents score"]
NUMBER_COLUMNS = ("winner number", "opponent number")
DATA_FILE = re.compile(r"^(?P<prefix>.+)-(?P<kind>results|ratings)\.(?:csv|tsv)$")


def _did_you_mean(word, candidates):
    close = difflib.get_close_matches(word, candidates, n=1, cutoff=0.75)
    return f" (did you mean {close[0]!r}?)" if close else ""


def check(results_dir=None, tournaments_csv=None, players_csv=None,
          milestone_dir=None, build=True) -> list[str]:
    """Every problem found in the corpus, as one line each; [] if none.

    The directories default to the live ones. ``build`` also runs the full
    replay, which always reads the live corpus, so tests of the checks on a
    scratch corpus turn it off.
    """
    results_dir = Path(results_dir or paths.RESULTS_DIR)
    tournaments_csv = Path(tournaments_csv or paths.TOURNAMENTS_CSV)
    players_csv = Path(players_csv or paths.PLAYERS_CSV)
    milestone_dir = Path(milestone_dir or paths.MILESTONE_DIR)

    problems = []
    entries = _check_tournament_list(tournaments_csv, problems)
    listed = {e.filename for e in entries if e.filename}
    files = _check_results_dir(results_dir, listed, problems)

    milestone = Milestone.load(milestone_dir)
    frozen = set(milestone.frozen_filenames) if milestone else set()
    players = PlayerDB.read_csv(players_csv)
    names = set(players.name_to_id)
    numbers = {canonical_player_number(n): name for n, name in players.id_to_name.items()}

    for e in entries:
        if not e.filename:
            continue
        found = files.get(e.filename, [])
        if not found:
            problems.append(
                f"tournaments.csv: {e.filename}: no results file; expected "
                f"results/{e.filename}-results.csv"
                + _did_you_mean(f"{e.filename}-results.csv",
                                [p.name for p in results_dir.iterdir()])
            )
        elif len(found) > 1:
            problems.append(
                f"tournaments.csv: {e.filename}: more than one results file "
                f"({', '.join(p.name for p in found)}); keep one"
            )
        elif e.filename not in frozen:
            problems.extend(check_results_file(found[0], names, numbers))

    if build and not problems:
        from coco_ratings.pipeline import process_old_results

        try:
            process_old_results(quiet=True)
        except Exception as ex:  # report it, whatever it is
            problems.append(f"building the ratings failed: {type(ex).__name__}: {ex}")
    return problems


def _check_tournament_list(path, problems):
    """The parseable entries of tournaments.csv, reporting the rest."""
    where = path.name
    entries = []
    seen = {}
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        if [normalize_header(c) for c in header[:7]] != [
            c.casefold() for c in TOURNAMENT_COLUMNS[:7]
        ]:
            problems.append(
                f"{where}: header should be {','.join(TOURNAMENT_COLUMNS)}, "
                f"got {','.join(header)}"
            )
            return entries
        for row in reader:
            line = f"{where}:{reader.line_num}"
            if not any(c.strip() for c in row):
                problems.append(f"{line}: blank line")
                continue
            if len(row) not in (7, 8):
                problems.append(
                    f"{line}: {len(row)} columns, expected 8 "
                    f"({','.join(TOURNAMENT_COLUMNS)}); check for an unquoted "
                    f"comma in a name"
                )
                continue
            e = TournamentEntry(*row)
            entries.append(e)
            try:
                datetime.strptime(e.date, "%Y-%m-%d")
            except ValueError:
                problems.append(f"{line}: Date {e.date!r} is not yyyy-mm-dd")
            if e.order.strip() and not e.order.strip().isdigit():
                problems.append(f"{line}: Order {e.order!r} is not a whole number")
            if not e.filename:
                continue
            if e.filename != e.filename.strip() or re.search(r"[\s/\\]", e.filename):
                problems.append(f"{line}: Filename {e.filename!r} has a space or slash")
            if e.filename in seen:
                problems.append(
                    f"{line}: Filename {e.filename} is already used on line "
                    f"{seen[e.filename]}"
                )
            seen.setdefault(e.filename, reader.line_num)
    return entries


def _check_results_dir(results_dir, listed, problems):
    """{filename: [results files]}, reporting data files nobody will read."""
    files = collections.defaultdict(list)
    expected = sorted(
        f"{p}-{kind}.csv" for p in listed for kind in ("results", "ratings")
    )
    for path in sorted(results_dir.iterdir()):
        if path.suffix.lower() not in (".csv", ".tsv"):
            continue
        m = DATA_FILE.match(path.name)
        if m and m["prefix"] in listed:
            if m["kind"] == "results":
                files[m["prefix"]].append(path)
            continue
        if m:
            why = f"no row in tournaments.csv has Filename {m['prefix']}"
        else:
            why = "not named <Filename>-results.csv or <Filename>-ratings.csv"
        problems.append(
            f"results/{path.name}: {why}, so it is never read"
            + _did_you_mean(path.name, expected)
        )
    return files


def check_results_file(path, names, numbers) -> list[str]:
    """Per-game problems in one results file.

    ``names`` is every name in data/players.csv; ``numbers`` maps each
    canonical player number to its name there.
    """
    path = Path(path)
    where = f"results/{path.name}"
    problems = []
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    with open(path, newline="") as f:
        reader = csv.reader(f, delimiter=sep)
        header = next(reader, [])
        if [normalize_header(c) for c in header[:6]] != RESULT_COLUMNS:
            return [
                f"{where}: header should start with Submitted On,Round,Winner,"
                f"Winners Score,Opponent,Opponents Score; got {','.join(header[:6])}"
            ]
        try:
            columns = find_number_columns(header, NUMBER_COLUMNS, where)
        except ParserError as ex:
            return [ex.message]

        rows_seen = {}
        opponents = collections.defaultdict(set)  # (round, player) -> {opponents}
        spelled = collections.defaultdict(set)  # number -> names, name -> numbers
        for row in reader:
            line = f"{where}:{reader.line_num}"
            if not any(c.strip() for c in row):
                problems.append(f"{line}: blank line")
                continue
            if len(row) < 6:
                problems.append(f"{line}: only {len(row)} columns")
                continue
            _, rnd, winner, w_score, opp, o_score = row[:6]
            rnd = rnd.strip()
            if not rnd:
                problems.append(f"{line}: no round")
            scores = []
            for label, s in (("winner's", w_score), ("opponent's", o_score)):
                try:
                    scores.append(int(s))
                except ValueError:
                    problems.append(f"{line}: {label} score {s!r} is not a number")
            if len(scores) == 2 and scores[0] < scores[1]:
                problems.append(
                    f"{line}: the winner scored less ({scores[0]}-{scores[1]}); "
                    f"are the two sides swapped?"
                )
            fingerprint = tuple(c.strip() for c in row[1:6])
            if fingerprint in rows_seen:
                problems.append(f"{line}: duplicate of line {rows_seen[fingerprint]}")
                continue
            rows_seen[fingerprint] = reader.line_num

            sides = []
            win_col, opp_col = columns or (None, None)
            for name, col in ((winner, win_col), (opp, opp_col)):
                number = cell(row, col) or ""
                if is_bye(name, number):
                    sides.append("Bye")
                    continue
                if not name.strip():
                    problems.append(f"{line}: a player's name is blank")
                    sides.append(None)
                    continue
                sides.append(_identify(line, name, number, columns, names,
                                       numbers, spelled, problems))
            if sides[0] == "Bye" and sides[1] == "Bye":
                problems.append(f"{line}: both sides are the bye")
                continue
            if sides[0] is not None and sides[0] == sides[1]:
                problems.append(f"{line}: {winner} is playing themselves")
                continue
            for me, them in ((sides[0], sides[1]), (sides[1], sides[0])):
                if me not in (None, "Bye") and them is not None:
                    opponents[(rnd, me)].add(them)

    # Meeting the same opponent more than once in a round is a playoff series;
    # two different opponents in one round is a mistake.
    for (rnd, player), opps in opponents.items():
        if len(opps) > 1:
            problems.append(
                f"{where}: {player} has {len(opps)} different opponents in "
                f"round {rnd} ({', '.join(sorted(opps))})"
            )
    for key, values in spelled.items():
        if len(values) > 1:
            problems.append(
                f"{where}: {key} appears as {' and '.join(sorted(values))}"
            )
    return problems


def _identify(line, name, number, columns, names, numbers, spelled, problems):
    """The key this side is filed under, reporting an unknown player."""
    if not columns:
        if name not in names:
            stripped = name.strip()
            hint = (f" (it has extra spaces: {stripped!r})" if stripped in names
                    else _did_you_mean(name, names))
            problems.append(
                f"{line}: {name!r} is not in data/players.csv{hint}; a new "
                f"player must be added there first"
            )
        return name
    if not number:
        problems.append(f"{line}: {name} has no player number")
        return name
    c = canonical_player_number(number)
    spelled[c].add(name.strip())
    spelled[name.strip()].add(c)
    if c not in numbers:
        problems.append(
            f"{line}: player number {number} ({name}) is not in data/players.csv"
        )
    elif numbers[c] != name.strip():
        problems.append(
            f"{line}: player number {number} is {numbers[c]} in "
            f"data/players.csv, but this file calls them {name}; is the number "
            f"wrong?"
        )
    return f"{name.strip()} ({c})"
