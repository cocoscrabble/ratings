"""In-memory ratings database that carries ratings forward across tournaments.

`RatingsDB` is the heart of the history replay: it rates one tournament at a
time, remembering each player's latest rating/deviation/career-games so the next
tournament they appear in starts from those values. This is a stopgap until an
actual database is put in place.
"""

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime

from coco_ratings.rating import Tournament


@dataclass
class PlayerRecord:
    name: str
    rating: float
    deviation: float
    games: int
    last_played: datetime

    @classmethod
    def from_tournament_player(cls, p):
        return cls(
            p.name, p.new_rating, p.new_rating_deviation, p.career_games, p.last_played
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

    @classmethod
    def from_tournament_player(cls, p, playerdb):
        try:
            coco_id = playerdb.get_id(p.name)
        except KeyError:
            print(f"MISSING NAME: {p.name}")
            coco_id = "9999"
        return cls(
            p.name,
            coco_id,
            p.init_rating,
            p.new_rating,
            round(p.init_rating_deviation, 2),
            round(p.new_rating_deviation, 2),
            p.career_games,
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

    def update(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                self.players[p.name] = PlayerRecord.from_tournament_player(p)
                self.report[p.name][tournament.name] = (
                    PlayerReport.from_tournament_player(p, self.playerdb)
                )

    def adjust_tournament(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                if p.name not in self.players:
                    continue
                dbp = self.players[p.name]
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
        self.adjust_tournament(t)
        t.calc_ratings(self.beta)
        self.update(t)
        return t
