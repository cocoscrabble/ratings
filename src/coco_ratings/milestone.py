"""Rating milestones: published ratings frozen in git, seeding the replay.

Without a milestone, every build replays the whole history, so any change to
the engine (a math fix, a reader change, a Python upgrade) rewrites every
rating back to 2021. A milestone commits the engine's *outputs* up to a point
and the replay starts from them instead:

- **Frozen tournaments are never rated again.** Their before/after ratings and
  deviations come from ``history.csv``, whatever the code now says.
- **Records are still derived from the files.** A frozen tournament is still
  read every build (the *record pass*), so wins, losses, spread and career
  games follow the results file. Correcting an old file (a missing bye, say)
  fixes the record without moving a rating.
- **Tournaments after the milestone are rated by the current code**, seeded
  from the carried state in ``state.csv``.

A change that would move any already-published rating after the milestone must
cut a new milestone first (``coco-rate milestone``); ``tests/test_pending.py``
enforces that. See ``plans/rating-milestones.md``.

Files in the milestone directory:

- ``manifest.json``: what is frozen (in rating order, with each results file's
  sha256), recorded amendments to frozen files, late additions, and how the
  milestone was cut.
- ``history.csv``: tournament, player key, old/new rating, old/new deviation.
- ``state.csv``: each player's carried rating state at the milestone.
- ``aliases.csv``: name -> player number, the identity the replay resolves.

Numbers are written with ``repr`` and read back to the same type, so a
milestone round-trips exactly: seeding from one is bit-identical to replaying
through it (``tests/test_milestone.py``).
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

FORMAT = 1

HISTORY_FIELDS = ["tournament", "key", "old_rating", "new_rating",
                  "old_deviation", "new_deviation"]
STATE_FIELDS = ["key", "name", "number", "rating", "deviation", "last_played"]


class MilestoneError(Exception):
    """The milestone and the files it froze disagree. Never guessed around:
    building ratings from a history that does not match its milestone would be
    the silent rewrite the milestone exists to prevent."""


def sha256_of(path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _number(text):
    """Read back a value written with repr: int if it was an int."""
    try:
        return int(text)
    except ValueError:
        return float(text)


def code_revision(root=None) -> str:
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return ""


@dataclass
class Milestone:
    through: str
    frozen: list[dict]  # [{"filename", "results_sha256"}], in rating order
    history: dict  # (tournament, key) -> {old_rating, new_rating, ...}
    state: dict  # key -> {name, number, rating, deviation, last_played}
    aliases: dict  # name -> number
    amendments: list[dict] = field(default_factory=list)
    late_additions: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)

    # -- reading -----------------------------------------------------------

    @classmethod
    def load(cls, directory) -> Milestone | None:
        """The milestone in ``directory``, or None if there is none."""
        directory = Path(directory)
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("format") != FORMAT:
            raise MilestoneError(
                f"{manifest_path}: format {manifest.get('format')!r}, this code "
                f"reads format {FORMAT}."
            )
        history = {}
        with open(directory / "history.csv", newline="") as f:
            for row in csv.DictReader(f):
                history[(row["tournament"], row["key"])] = {
                    "old_rating": _number(row["old_rating"]),
                    "new_rating": _number(row["new_rating"]),
                    "old_deviation": _number(row["old_deviation"]),
                    "new_deviation": _number(row["new_deviation"]),
                }
        state = {}
        with open(directory / "state.csv", newline="") as f:
            for row in csv.DictReader(f):
                state[row["key"]] = {
                    "name": row["name"],
                    "number": row["number"] or None,
                    "rating": _number(row["rating"]),
                    "deviation": _number(row["deviation"]),
                    "last_played": datetime.fromisoformat(row["last_played"]),
                }
        with open(directory / "aliases.csv", newline="") as f:
            aliases = {row["name"]: row["number"] for row in csv.DictReader(f)}
        return cls(
            through=manifest["through"],
            frozen=manifest["frozen"],
            history=history,
            state=state,
            aliases=aliases,
            amendments=manifest.get("amendments", []),
            late_additions=manifest.get("late_additions", []),
            manifest=manifest,
        )

    @property
    def frozen_filenames(self) -> list[str]:
        return [f["filename"] for f in self.frozen]

    # -- checking ----------------------------------------------------------

    def plan(self, entries, results):
        """Split the chronology into (frozen entries, entries to rate).

        ``entries`` is the sorted TournamentDB list; ``results`` maps a filename
        to its results file. Raises MilestoneError for anything that would
        quietly disturb frozen history:

        - a frozen tournament missing from tournaments.csv or from results/;
        - a frozen results file that changed with no recorded amendment;
        - a tournament not frozen but sorting at or before the milestone, unless
          it is a recorded late addition.

        Frozen tournaments keep the order they were rated in, whatever their
        row now says: a corrected date is display only.
        """
        by_name = {e.filename: e for e in entries if e.filename}
        problems = []
        frozen_entries = []
        for f in self.frozen:
            name = f["filename"]
            entry = by_name.get(name)
            if entry is None:
                problems.append(f"{name}: frozen, but missing from tournaments.csv")
                continue
            path = results.get(name)
            if path is None:
                problems.append(f"{name}: frozen, but its results file is gone")
                continue
            current = sha256_of(path)
            if current != f["results_sha256"] and current not in self._amended(name):
                problems.append(
                    f"{name}: frozen results file changed with no recorded "
                    f"amendment (sha256 {current}). Ratings for it are frozen, "
                    f"so record the change in milestone/manifest.json "
                    f"'amendments' with a reason."
                )
            frozen_entries.append(entry)

        frozen = set(self.frozen_filenames)
        through = by_name.get(self.through)
        cutoff = _sort_key(through) if through else None
        late, rest = [], []
        for e in entries:
            if not e.filename or e.filename in frozen:
                continue
            if cutoff is not None and _sort_key(e) <= cutoff:
                if e.filename in self.late_additions:
                    late.append(e)
                else:
                    problems.append(
                        f"{e.filename}: dated {e.date}, at or before the "
                        f"milestone ({self.through}), but not frozen. History "
                        f"before the milestone cannot be re-rated; list it in "
                        f"milestone/manifest.json 'late_additions' to rate it "
                        f"now, against the milestone's ratings."
                    )
            else:
                rest.append(e)
        if problems:
            raise MilestoneError("\n".join(problems))
        return frozen_entries, late + rest

    def _amended(self, filename):
        return {
            a["results_sha256"] for a in self.amendments if a["filename"] == filename
        }

    # -- the frozen pass ---------------------------------------------------

    def apply(self, ratingsdb, tournament):
        """Fill a parsed frozen tournament's ratings from the history.

        Called in place of ``calc_ratings``. Everything the reader derived
        (record, spread, game counts, identity) stands; only the rating fields
        are overwritten. A player the history does not know, or one it expects
        who is not there, means identity drifted under the frozen file, and is
        an error rather than a guess.
        """
        seen = set()
        for s in tournament.sections:
            for p in s.get_players():
                key = ratingsdb.key_for(p)
                h = self.history.get((tournament.name, key))
                if h is None:
                    raise MilestoneError(
                        f"{tournament.name}: {p.name} ({key}) is in the results "
                        f"file but not in the milestone's history."
                    )
                seen.add(key)
                p.init_rating = h["old_rating"]
                p.init_rating_deviation = h["old_deviation"]
                p.new_rating = h["new_rating"]
                p.new_rating_deviation = h["new_deviation"]
        expected = {k for (t, k) in self.history if t == tournament.name}
        if expected - seen:
            raise MilestoneError(
                f"{tournament.name}: the milestone's history has "
                f"{sorted(expected - seen)}, who are not in the results file."
            )

    def restore_state(self, ratingsdb):
        """After the frozen pass: the carried rating state is the milestone's.

        Ratings and deviations already agree (they come from the history), and
        are checked. ``last_played`` is taken from the milestone because it
        ages deviation, so it is a rating input: a corrected tournament date
        must not move it. Game counts are left as the record pass derived them.
        """
        for key, s in self.state.items():
            rec = ratingsdb.players.get(key)
            if rec is None:
                raise MilestoneError(f"{s['name']} ({key}): in state.csv, never seen")
            if (rec.rating, rec.deviation) != (s["rating"], s["deviation"]):
                raise MilestoneError(
                    f"{s['name']} ({key}): carried {rec.rating}/{rec.deviation}, "
                    f"milestone says {s['rating']}/{s['deviation']}"
                )
            rec.last_played = s["last_played"]
        extra = set(ratingsdb.players) - set(self.state)
        if extra:
            raise MilestoneError(f"players not in state.csv: {sorted(extra)}")
        for name, number in self.aliases.items():
            ratingsdb.aliases.setdefault(name, number)


def _sort_key(entry):
    return (entry.date, entry.sort_order, entry.filename)


# -- cutting -----------------------------------------------------------------


def cut(directory, ratingsdb, rated, results, previous=None, beta=5):
    """Write a milestone freezing everything in ``ratingsdb``.

    ``rated`` is the list of filenames ``ratingsdb`` has processed, in order
    (frozen ones first); ``results`` maps filename -> results file. The new
    milestone is a superset of ``previous``: an existing history row that would
    change is refused, so cutting can only add frozen history.
    """
    directory = Path(directory)
    history = {}
    for key, reports in ratingsdb.report.items():
        for tournament, rep in reports.items():
            history[(tournament, key)] = {
                "old_rating": rep.old_rating,
                "new_rating": rep.new_rating,
                "old_deviation": rep.old_deviation,
                "new_deviation": rep.new_deviation,
            }
    if previous is not None:
        changed = [k for k, v in previous.history.items() if history.get(k) != v]
        if changed:
            raise MilestoneError(
                f"cutting would change {len(changed)} frozen history row(s), "
                f"e.g. {changed[:3]}"
            )

    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "history.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HISTORY_FIELDS)
        order = {name: i for i, name in enumerate(rated)}
        for (tournament, key), h in sorted(
            history.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])
        ):
            w.writerow([tournament, key] + [repr(h[f]) for f in HISTORY_FIELDS[2:]])
    with open(directory / "state.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(STATE_FIELDS)
        for key in sorted(ratingsdb.players):
            r = ratingsdb.players[key]
            w.writerow([key, r.name, r.number or "", repr(r.rating),
                        repr(r.deviation), r.last_played.isoformat()])
    with open(directory / "aliases.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "number"])
        for name in sorted(ratingsdb.aliases):
            w.writerow([name, ratingsdb.aliases[name]])

    manifest = {
        "format": FORMAT,
        "through": rated[-1],
        "cut_on": date.today().isoformat(),
        "code_rev": code_revision(directory.parent),
        "python": platform.python_version(),
        "beta": beta,
        "frozen": [
            {"filename": name, "results_sha256": sha256_of(results[name])}
            for name in rated
        ],
        # Kept as the record of what changed under frozen ratings; the new
        # hashes above already accept those files.
        "amendments": previous.amendments if previous else [],
        "late_additions": [],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest
