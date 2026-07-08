"""Core data model for the ratings engine.

This is the lowest layer: pure data structures with no dependency on the file
readers/writers (``io``) or the engine (``rating``). Both of those import from
here, which keeps the dependency graph acyclic.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import math


MAX_DEVIATION = 150.0
UNRATED_INIT_RATING = 1500


def show_exception(ex):
    raise Exception from ex


@dataclass
class GameResult:
    round: int
    opponent: "Player"
    score: int
    opp_score: int

    @property
    def spread(self):
        return self.score - self.opp_score

    def __str__(self):
        return f"{self.opponent.name:<24s} {self.score:3d} - {self.opp_score:3d}"

    @property
    def outcome(self):
        if self.score > self.opp_score:
            return "W"
        if self.score == self.opp_score:
            return "T"
        if self.score < self.opp_score:
            return "L"


class Player:
    """Data for a single player."""

    def __init__(
        self,
        name,
        *,
        init_rating=0,
        init_rating_deviation=0.0,
        career_games=0,
        is_unrated=False,
        last_played=None,
    ):
        self.name = name
        self.career_games = career_games
        self.is_unrated = is_unrated
        self.set_init_rating(init_rating, init_rating_deviation)
        self.last_played = last_played or datetime(1999, 12, 31)

        # Always initialized to zero when creating the player
        self.wins = 0.0
        self.losses = 0.0
        self.spread = 0
        self.rating_change = 0
        self.new_rating = 0
        self.new_rating_deviation = 0.0
        self.games = []  # list of Game objects

    @classmethod
    def new_unrated(cls, name):
        return cls(
            name=name,
            init_rating=UNRATED_INIT_RATING,
            init_rating_deviation=MAX_DEVIATION,
            last_played=datetime.today(),
            is_unrated=True,
        )

    def __str__(self):
        return self.name

    def tally_results(self):
        self.update_career_games()
        for g in self.games:
            self.add_game_result(g.spread)

    def set_init_rating(self, rating, dev=MAX_DEVIATION):
        # The initial rating should never be < 100, if it is we have probably
        # encountered a fake value for an unrated player.
        if rating < 100:
            self.init_rating = UNRATED_INIT_RATING
            self.is_unrated = True
        else:
            self.init_rating = rating

        self.init_rating_deviation = dev

        if self.init_rating_deviation == 0:
            self.init_rating_deviation = MAX_DEVIATION
        else:
            self.init_rating_deviation = dev

        self.new_rating = rating
        self.new_rating_deviation = dev

    def add_game_result(self, spr):
        self.spread += spr
        if spr == 0:
            self.wins += 0.5
            self.losses += 0.5
        elif spr > 0:
            self.wins += 1
        else:
            self.losses += 1

    def update_career_games(self):
        for game in self.games:
            if game.opponent != self and game.opponent != "Zz Bye":
                self.career_games += 1

    def get_score_by_round(self, r):
        return self.games[r].score

    def get_opponent_by_round(self, r):
        return self.games[r].opponent

    def get_opponents(self):
        """Returns a list of all opponents."""
        return [g.opponent for g in self.games]

    def adjust_initial_deviation(self, tournament_date):
        try:
            c = 10
            inactive_days = int((tournament_date - self.last_played).days)
            init = self.init_rating_deviation
            new = math.sqrt((init * init) + (c * c * inactive_days))
            self.init_rating_deviation = min(new, MAX_DEVIATION)
            if abs(init - self.init_rating_deviation) > 1e-5:
                logging.info(
                    "Adjusted rating deviation for %s: %f -> %f",
                    self.name,
                    init,
                    self.init_rating_deviation,
                )
        except Exception as ex:
            show_exception(ex)


class Section:
    """One section of a tournament."""

    def __init__(self, name):
        self.players = []  # List of Player objects
        self.highgame = {}  # should be dict containing Player, Round, Score
        self.name = name

    def get_players(self):
        return self.players

    def get_rated_players(self):
        return [p for p in self.players if not p.is_unrated]

    def get_unrated_players(self):
        return [p for p in self.players if p.is_unrated]

    def show(self):
        for p in self.players:
            print(f"Player: {p.name}")
            for i, g in enumerate(p.games):
                print(f"{i + 1:>2d}  {g}")
