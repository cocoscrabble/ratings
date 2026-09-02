"""In-memory ratings database that carries ratings forward across tournaments.

`RatingsDB` is the heart of the history replay: it rates one tournament at a
time, remembering each player's latest rating/deviation/career-games so the next
tournament they appear in starts from those values. This is a stopgap until an
actual database is put in place.
"""

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime

from coco_ratings.rating import Tournament


# Stand-in id for a rated player with no row in data/players.csv. The name is
# collected in RatingsDB.missing_ids so the caller can report it once, rather
# than printing per player per tournament.
UNKNOWN_COCO_ID = "9999"


@dataclass
class PlayerRecord:
    name: str
    rating: float
    deviation: float
    games: int
    last_played: datetime
    number: str | None = None

    @classmethod
    def from_tournament_player(cls, p):
        return cls(
            p.name,
            p.new_rating,
            p.new_rating_deviation,
            p.career_games,
            p.last_played,
            p.number,
        )


@dataclass
class PlayerReport:
    name: str
    coco_id: str
    old_rating: float
    new_rating: float
    old_deviation: float
    new_deviation: float
    games: int
    wins: float
    losses: float
    spread: int

    @classmethod
    def from_tournament_player(cls, p, coco_id):
        return cls(
            p.name,
            coco_id,
            p.init_rating,
            p.new_rating,
            round(p.init_rating_deviation, 2),
            round(p.new_rating_deviation, 2),
            p.career_games,
            p.wins,
            p.losses,
            p.spread,
        )


class CSVRatingsFileWriter:
    """Write ratings in csv format.

    CSV format:
        name, rating, rating deviation
    """

    def headers(self):
        return ["Name", "Rating", "Deviation", "Games played"]

    def row(self, p):
        return [p.name, p.rating, p.deviation, p.games]

    def write_file(self, output_file, players):
        players = sorted(players, key=lambda p: -p.rating)
        with open(output_file, "w", newline="") as f:
            self.write(f, players)

    def write(self, f, players):
        writer = csv.writer(f)
        writer.writerow(self.headers())
        for p in players:
            writer.writerow(self.row(p))


class RatingsDB:
    """Ratings database."""

    def __init__(self, playerdb, beta: float = 5):
        self.playerdb = playerdb
        # beta is the rating-system tuning parameter; simulations vary it.
        self.beta = beta
        self.players = {}
        self.report = defaultdict(dict)
        # How many tournaments came in each form, over the whole replay. The
        # name-keyed path is supported for as long as the Google Form exists,
        # so this is a measure of a migration's progress, not a warning.
        self.keyed_by = Counter()
        # name -> storage key, for players whose record is filed under a number
        # while some files still refer to them only by name. See key_for().
        self.aliases = {}
        # Rated names with no row in data/players.csv, accumulated over the
        # whole replay. A name missing here is usually a typo that has split one
        # player in two, so it is worth reporting — but once, at the end.
        self.missing_ids = set()

    def coco_id_for(self, player):
        """The player's CoCo id, remembering the name if there isn't one.

        A number-bearing file has already answered this question, so trust it;
        data/players.csv is the name->number join that exists only because the
        Google Form export cannot carry a number.
        """
        if player.number:
            return player.number
        try:
            return self.playerdb.get_id(player.name)
        except KeyError:
            self.missing_ids.add(player.name)
            return UNKNOWN_COCO_ID

    def key_for(self, player):
        """The key this player's carried-forward record lives under.

        Ratings carry forward across the whole history, so this key decides
        whether a player continues their career or starts a new one. The corpus
        is name-keyed and Baxter's files are number-keyed, and the *same person*
        appears in both — so the two forms have to resolve to one record.

        A number is definitive when the file gives one. The first time someone
        turns up with a number after a career's worth of name-keyed
        tournaments, their record is moved onto the number rather than left
        behind: not doing so would silently reset them to unrated, which is the
        exact "one person split in two" failure the shared canonicalizer exists
        to prevent.

        The name->number alias is then remembered, so a later Google Form file
        that knows them only by name still finds the same record.
        """
        if not player.number:
            return self.aliases.get(player.name, player.name)

        number = player.number
        if number not in self.players and player.name in self.players:
            self.players[number] = self.players.pop(player.name)
            if player.name in self.report:
                self.report[number] = self.report.pop(player.name)
        # First number wins. Two same-named players in a number-keyed file are
        # two people, but which of them owns the name-keyed history is not
        # recoverable from the files — nothing ever recorded it. Claiming it for
        # the first is arbitrary; the alternative is refusing an import that is
        # otherwise correct.
        self.aliases.setdefault(player.name, number)
        return number

    def update(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                key = self.key_for(p)
                self.players[key] = PlayerRecord.from_tournament_player(p)
                self.report[key][tournament.name] = (
                    PlayerReport.from_tournament_player(p, self.coco_id_for(p))
                )

    def adjust_tournament(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                key = self.key_for(p)
                if key not in self.players:
                    continue
                dbp = self.players[key]
                # if p.init_rating != dbp.rating:
                #     print(f"Adjusting: {p.name} : {p.init_rating} -> {dbp.rating}")
                p.init_rating = dbp.rating
                p.init_rating_deviation = dbp.deviation
                p.career_games += dbp.games
                p.is_unrated = False
                p.last_played = dbp.last_played
                p.adjust_initial_deviation(tournament.date)
                p.last_played = tournament.date

    def process_one_tournament(self, rat_file, res_file, name, date):
        t = Tournament(rat_file, res_file, name, date)
        self.keyed_by[t.keyed_by] += 1
        self.adjust_tournament(t)
        t.calc_ratings(self.beta)
        self.update(t)
        return t
