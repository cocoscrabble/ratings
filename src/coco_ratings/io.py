"""File readers and writers for the ratings engine.

Reads/writes the various tournament result and ratings-list formats (CSV/TSV,
AUPAIR ``.tou``, and ``.RT``) into and out of the ``types`` data model. Depends
only on ``types``; the ``rating`` engine wires these together.
"""

import collections
import csv
from dataclasses import dataclass
from datetime import datetime
import itertools
import logging
import re
import sys

from coco_ratings.types import MAX_DEVIATION, GameResult, Player, Section

# Module logger, not the root one: this is a library, and an application
# importing it must be able to quiet the engine without silencing itself.
logger = logging.getLogger(__name__)


class ParserError(Exception):
    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message

    def __str__(self):
        return f"{self.message}\n{self.line}"


def parse_int(s, line="", field="Score"):
    try:
        return int(s)
    except ValueError:
        msg = f"{field} field contained a non-digit: {s}"
        raise ParserError(line, msg)


def normalize_header(cell):
    """A header cell reduced to something worth comparing.

    Real files in ``results/`` are messier than the format description: some
    carry a UTF-8 BOM, some quote every cell, and many have a tail of empty
    columns. Matching a normalized name is what lets the number columns be
    found without caring about any of that.
    """
    return cell.lstrip("\ufeff").strip().casefold()


def find_number_columns(header, wanted, file=""):
    """Locate the optional player-number columns, or return None.

    ``wanted`` is the pair of header names to look for. Returns their indices
    when both are present and None when neither is, which is the header
    dispatch: a file is number-bearing or it is not, and the decision is made
    once here rather than per row.

    Finding exactly one of the pair raises. A file half-way between the two
    forms is malformed, and resolving it row by row would silently key some
    players by number and others by name -- the one outcome worse than
    refusing, because it splits people in two without saying so.
    """
    cells = [normalize_header(c) for c in header]
    found = {name: cells.index(name) for name in wanted if name in cells}
    if not found:
        return None
    if len(found) != len(wanted):
        missing = ", ".join(repr(n) for n in wanted if n not in found)
        raise ParserError(
            ",".join(header),
            f"{file}: number-bearing header is missing {missing}. A results "
            f"file carries player numbers for both players or for neither.",
        )
    return tuple(found[name] for name in wanted)


def cell(row, index):
    """``row[index]``, or None if the row is short or the cell is empty.

    Trailing empty cells are routinely dropped, so a number column can be
    absent from an individual row of a file whose header declares it.
    """
    if index is None or index >= len(row):
        return None
    return row[index].strip() or None


# -----------------------------------------------------
# Result file


@dataclass
class ParsedResult:
    opponent_id: int
    score: int


@dataclass
class ParsedPlayerResults:
    player_name: str
    results: list[ParsedResult]


class ParsedSection:
    def __init__(self, name):
        self.name = name
        self.player_results = []

    def add_player_results(self, entry):
        self.player_results.append(entry)


class ResultsReader:
    """Read a results file into Player and Section data."""

    # Set by each subclass before player_for() is called.
    tournament_date: datetime

    # Which identity the file keyed its players by: "number" if it carried
    # player numbers, "name" otherwise. Readers that cannot carry numbers at
    # all (.tou) leave this at "name". Exposed so callers can report which
    # corpus is which, and so retiring the name-keyed path has a way to
    # measure its own progress.
    keyed_by = "name"

    def __init__(self, player_list):
        self.player_list = player_list
        self.sections = []

    def player_for(self, name, number=None):
        player = self.player_list.find_or_add_player(name, number)
        if not player.is_unrated:
            player.adjust_initial_deviation(self.tournament_date)
        player.last_played = self.tournament_date
        return player

    def player_for_name(self, name):
        return self.player_for(name)


class TouReader(ResultsReader):
    """Read AUPAIR's .tou file format."""

    def parse(self, file):
        """Populates self.player_list with game results."""
        with open(file) as f:
            lines = f.readlines()
            try:
                self.parse_lines(lines)
            except ParserError as e:
                print(e)

    def parse_lines(self, lines):
        # Parse the file into our internal data structures.
        header, *results = lines
        self.parse_header(header)
        self.parsed_sections = self.parse_results(results)
        self.process_sections()

    def parse_header(self, header):
        # First line: *M31.12.1969 Tournament Name
        date, self.tournament_name = header.rstrip().split(maxsplit=1)
        try:
            date = date[2:]  # strip off the '*M'
            self.tournament_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            print(f"Cannot parse tournament date: {date} as dd.mm.yyyy")
            print("Using today's date")
            self.tournament_date = datetime.today()

    def parse_results(self, results):
        sections = []
        for line in results:
            if len(line) == 0 or line.startswith(" "):
                continue

            line = line.strip()
            if line == "*** END OF FILE ***":
                break
            elif line.startswith("*"):
                # We have begun a new section, designated by "*SectionName"
                sections.append(ParsedSection(line[1:]))
                continue
            elif len(line) < 3:
                # ignore ridiculously short lines
                continue

            player_results = self.parse_result_line(line)
            if not player_results:
                continue  # this is a high word listed at the top of the file
            sections[-1].add_player_results(player_results)
        return sections

    def process_sections(self):
        for s in self.parsed_sections:
            # Collect all the players in the section
            players = [self.player_for_name(pr.player_name) for pr in s.player_results]

            # 1. Create a (players x rounds) matrix of GameResults,
            # filling in opponent and player_score, and leaving
            # opponent_score empty
            section_results = []
            for pr, player in zip(s.player_results, players):
                game_results = []
                for i, result in enumerate(pr.results):
                    try:
                        opponent = players[result.opponent_id - 1]
                    except IndexError:
                        print(
                            f"Invalid opponent id {result.opponent_id} for"
                            f" player {player.name} in section {s.name}"
                        )
                        sys.exit(1)
                    round = i + 1
                    # opp_score is filled in from the opponent's half-result below.
                    gr = GameResult(round, opponent, result.score, opp_score=None)  # type: ignore[arg-type]
                    game_results.append(gr)
                section_results.append(game_results)

            # 2. Now iterate through the results again, and for each
            # round, look up the opponent's GameResult for that round. The
            # opponent's opponent_score will be the player's score.
            for pr in s.player_results:
                for i, result in enumerate(pr.results):
                    opp_gr = section_results[result.opponent_id - 1][i]
                    opp_gr.opp_score = result.score

            # 3. Now that we have fully filled in both sides of each
            # GameResult from the two half-results, we can add them to the
            # Player and then update the player's results fields.
            for sr, player in zip(section_results, players):
                player.games = sr
                player.tally_results()

            # 4. Now write out the fully parsed and populated Section
            section = Section(s.name)
            section.players = players
            self.sections.append(section)

    def parse_result_line(self, line):
        """Parses result line into (name, [ParsedResult])."""
        # TOU FORMAT:
        # Mark Nyman           2488  16 2458  +4 2489 +25 2392   2  345  +8  348
        # Name       (score with prefix) (opponent number) (score with prefix) (opponent number)
        # Score Prefixes: 1 = Tie, 2 = Win
        # Opponent Prefixes: + = player went first
        parts = line.split()
        # Read the first n parts with an alphabet in them as the name, and
        # everything else as the scores.
        name = list(itertools.takewhile(lambda x: re.search("[a-zA-Z]", x), parts))
        scores = parts[len(name) :]
        name = " ".join(name)
        if len(scores) < 2:
            # High score line; ignore it
            return None

        player_scores = []
        for i in range(0, len(scores), 2):
            score, opp = scores[i], scores[i + 1]
            score = parse_int(score, line) % 1000  # ignore the win/tie prefix
            opp = parse_int(opp, line)  # ignore the + prefix too
            player_scores.append(ParsedResult(opp, score))
        return ParsedPlayerResults(name, player_scores)


class ResultCSVReader(ResultsReader):
    """Read a csv exported from google sheets, or produced by Baxter.

    Two header shapes are valid input:

    - ``Submitted On, Round, Winner, Winners Score, Opponent, Opponents
      Score`` -- the Google Form export. Players are identified by name,
      joined to a canonical player through ``data/players.csv``.
    - the same six columns with ``Winner Number, Opponent Number`` **appended**
      -- what Baxter produces. The number is the identity, so two players
      sharing a name stay two players.

    The number columns are appended rather than interleaved because the six
    legacy fields are unpacked positionally below: anything inserted among them
    shifts every later field. Appending puts them in ``*rest``, which is why
    Baxter's files already parsed here before this reader knew about them. See
    plans/baxter-integration.md phase 2a.

    The Form export can never carry numbers -- players type their own names
    into it -- so the name-keyed path is a supported format, not a fallback
    waiting to rot.
    """

    NUMBER_COLUMNS = ("winner number", "opponent number")

    def __init__(self, player_list, name, date):
        super().__init__(player_list)
        self.results = collections.defaultdict(list)
        self.tournament_date = date
        self.tournament_name = name
        # How each player in this file was written, filed under the identity
        # key they resolved to. Keeping them lets the section be rebuilt in
        # file order without deriving identity a second time.
        self.names = {}
        self.numbers = {}
        self.winner_col = None
        self.opponent_col = None

    def parse(self, file):
        """Populates self.player_list with game results."""
        sep = "\t" if file.endswith(".tsv") else ","
        with open(file) as f:
            reader = csv.reader(f, delimiter=sep)
            header = next(reader)
            columns = find_number_columns(header, self.NUMBER_COLUMNS, file)
            self.keyed_by = "name" if columns is None else "number"
            if columns:
                self.winner_col, self.opponent_col = columns
            for row in reader:
                self.parse_row(row)

        for key, games in self.results.items():
            player = self.player_for_key(key)
            player.games = games
            player.tally_results()

        section = Section("main")
        section.players = [self.player_for_key(key) for key in self.results]
        self.sections.append(section)

    def player_for_key(self, key):
        return self.player_for(self.names[key], self.numbers.get(key))

    def add_player(self, name, number):
        """Register one appearance; return the player and the key they file under."""
        player = self.player_for(name, number)
        self.names[player.key] = name
        if number:
            self.numbers[player.key] = number
        return player, player.key

    def parse_row(self, row):
        _time, round, winner, win_score, opp, opp_score, *rest = row
        p1, k1 = self.add_player(winner, cell(row, self.winner_col))
        p2, k2 = self.add_player(opp, cell(row, self.opponent_col))
        win_score = parse_int(win_score, row)
        opp_score = parse_int(opp_score, row)
        g1 = GameResult(round=round, opponent=p2, score=win_score, opp_score=opp_score)
        g2 = GameResult(round=round, opponent=p1, score=opp_score, opp_score=win_score)
        self.results[k1].append(g1)
        self.results[k2].append(g2)


class ResultWriter:
    """Write out tournament results."""

    def headers(self):
        return ["Name", "Record", "Spread", "Old Rating", "New Rating", "New Deviation"]

    def get_sorted_players(self, section):
        return sorted(
            section.get_players(),
            key=lambda x: (x.wins * 100000) + x.spread,
            reverse=True,
        )

    def row(self, p):
        return [
            p.name,
            f"{p.wins}-{p.losses}",
            p.spread,
            p.init_rating,
            p.new_rating,
            p.new_rating_deviation,
        ]


class TabularResultWriter(ResultWriter):
    """Write out the results in tabular format."""

    def __init__(self):
        self.col_fmt = "{:28} {:10} {:7} {:8} {:8} {:8}\n"

    def write_file(self, output_file, tournament):
        with open(output_file, "w") as f:
            self.write(f, tournament)

    def write(self, f, tournament):
        f.write(f"{tournament.name}\n{tournament.date.date()}\n")
        for s in tournament.sections:
            self._write_section(f, s)

    def _write_section(self, out, section):
        out.write("Section {:1}\n".format(section.name))
        header = self.col_fmt.format(*self.headers())
        out.write(header)

        for p in self.get_sorted_players(section):
            out.write(self.col_fmt.format(*self.row(p)))
        out.write("\n")  # section break

        for p in section.get_unrated_players():
            out.write("{:21} is unrated \n".format(p.name))
        out.write("\n")  # section break


class CSVResultWriter(ResultWriter):
    """Write out results in .csv format."""

    def write_file(self, output_file, tournament):
        with open(output_file, "w", newline="") as f:
            self.write(f, tournament)

    def write(self, f, tournament):
        writer = csv.writer(f)
        for s in tournament.sections:
            self._write_section(writer, s)

    def _write_section(self, out, section):
        out.writerow(self.headers())
        for p in self.get_sorted_players(section):
            out.writerow(self.row(p))
        for p in section.get_unrated_players():
            out.writerow(["Unrated:", p.name])


class TouResultWriter(ResultWriter):
    """Write out the tournament in .TOU format."""

    def write_file(self, output_file, tournament):
        with open(output_file, "w") as f:
            self.write(f, tournament)

    def write(self, f, tournament):
        f.write(f"*M{tournament.date.strftime('%d.%m.%Y')} {tournament.name}\n")
        for s in tournament.sections:
            self._write_section(f, s)
        f.write("*** END OF FILE ***\n")

    def _write_section(self, out, section):
        out.write(f"*{section.name}\n")
        out.write(f"{0:39}\n")
        players = self.get_sorted_players(section)
        last_round = max(int(g.round) for p in players for g in p.games)

        numbers = {}
        for i, p in enumerate(players):
            numbers[p.name] = i + 1

        for p in players:
            if p.name.lower() == "bye":
                continue
            row = [self._format_name(p.name)]
            games = {g.round: g for g in p.games}
            for round in range(last_round):
                g = games.get(str(round + 1))
                if g:
                    row.append(self._format_game(p, g, numbers))
                else:
                    # No result for round
                    row.append(self._format("0", 0, numbers[p.name]))

            out.write(" ".join(row))
            out.write("\n")

    def _format_name(self, name):
        # special-case cbb
        if name.lower().startswith("conrad bassett"):
            name = "Conrad Bassett"
        return f"{name:20}"

    def _format_game(self, p, g, numbers):
        prefix = {"W": "2", "L": " ", "T": "1"}[g.outcome]
        if g.opponent.name.lower() == "bye":
            opp = numbers[p.name]
        else:
            opp = numbers[g.opponent.name]
        return self._format(prefix, g.score, opp)

    def _format(self, prefix, score, opp):
        return f"{prefix}{score:0>3}{opp:>4}"


# -----------------------------------------------------
# Ratings file


class RTFileReader:
    """Reads the .RT format."""

    def parse(self, ratfile):
        players = {}
        with open(ratfile) as f:
            next(f)  # skip headings
            for row in f:
                p = self._read_player(row)
                players[p.name] = p
        return players

    def _read_player(self, row):
        # nick = row[0:4]
        # state = row[5:8]
        name = row[9:29].strip()
        career_games = int(row[30:34])
        rating = int(row[35:39])
        last_played = self._read_date(row)
        try:
            rating_deviation = float(row[49:])
        except (ValueError, IndexError):
            rating_deviation = MAX_DEVIATION
        return Player(
            name=name,
            init_rating=rating,
            init_rating_deviation=rating_deviation,
            career_games=career_games,
            last_played=last_played,
            is_unrated=False,
        )

    def _read_date(self, row):
        # DEVELOPING TOLERANCE FOR HORRIBLY FORMATTED TOU FILES GRRR!
        # Try reading the date in three different places (40, 39, 41)
        # and two different formats (yyyymmdd and yyyyddmm)
        for col in (40, 39, 41):
            for fmt in ("%Y%m%d", "%Y%d%m"):
                try:
                    # Return as soon as we parse a date.
                    return datetime.strptime(row[col : col + 8], fmt)
                except ValueError:
                    logger.debug(f"Failed parse: {fmt} @ {col}\n  {row}\n")

        # If we reach here we have not found a date anywhere we've looked.
        logger.debug(f"Could not parse last played date\n  {row}\n")
        return datetime.strptime("20060101", "%Y%m%d")


class RTFileWriter:
    """Writes the .RT format."""

    def __init__(self):
        self.col_fmt = "{:9}{:28}{:5}{:5} {:9}{:6}\n"

    def _header(self):
        return self.col_fmt.format(
            "Nick", "Name", "Games", " Rat", "last_played", "New Dev"
        )

    def write_file(self, file, players):
        with open(file, "w") as f:
            self.write(f, players)

    def write(self, f, players):
        f.write(self._header())
        for p in players:
            out = self.col_fmt.format(
                "-",
                p.name,
                p.career_games,
                p.new_rating,
                p.last_played.strftime("%Y%m%d"),
                p.new_rating_deviation,
            )
            f.write(out)


class CSVRatingsFileReader:
    """Read ratings in csv format.

    CSV format exported from COCO google sheets:
        name, rating, email

    A ``Number`` column may be **appended**, for the same reason it is appended
    to the results file: ``parse_row`` unpacks positionally, so a column
    inserted before ``Rating`` would be read as the rating. Nothing produces
    the number-bearing form yet -- Baxter exports results only -- but the two
    files are a pair, so each is dispatched on its own header rather than
    assuming the other's shape.
    """

    NUMBER_COLUMNS = ("number",)

    # Set by parse(); see ResultsReader.keyed_by.
    keyed_by = "name"

    def parse(self, file):
        players = {}
        sep = "\t" if file.endswith(".tsv") else ","
        with open(file) as f:
            reader = csv.reader(f, delimiter=sep)
            header = next(reader)
            columns = find_number_columns(header, self.NUMBER_COLUMNS, file)
            self.keyed_by = "name" if columns is None else "number"
            number_col = columns[0] if columns else None
            for row in reader:
                p = self.parse_row(row, cell(row, number_col))
                players[p.key] = p
        return players

    def parse_row(self, row, number=None):
        name, rating, *_rest = row
        career_games = 0
        rating = parse_int(rating, row, field="Rating")
        rating_deviation = MAX_DEVIATION
        is_unrated = rating == 0
        return Player(
            name=name,
            number=number,
            init_rating=rating,
            init_rating_deviation=rating_deviation,
            career_games=career_games,
            is_unrated=is_unrated,
        )
