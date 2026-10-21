"""Core data model for the ratings engine.

This is the lowest layer: pure data structures with no dependency on the file
readers/writers (``io``) or the engine (``rating``). Both of those import from
here, which keeps the dependency graph acyclic.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import math

from coco_ratings.identity import canonical_player_number

# Module logger, not the root one: this is a library, and an application
# importing it must be able to quiet the engine without silencing itself.
logger = logging.getLogger(__name__)


MAX_DEVIATION = 150.0
UNRATED_INIT_RATING = 1500

# How results files spell the bye. Baxter writes "Bye" with the reserved number
# BYE; the hand-kept corpus has only ever used "Bye", but these spellings were
# recognised by the old ratings-file writer and are kept so an older file still
# reads correctly. Compared casefolded.
BYE_NAMES = frozenset(
    n.casefold()
    for n in (
        "Bye", "A Bye", "B Bye", "Y Bye", "Z Bye", "Yy bye", "Zy bye",
        "Zz Bye", "ZZ Bye", "Bye One", "Bye Two", "Bye Three", "Bye Four",
    )
)
BYE_NUMBER = "BYE"


def is_bye(name, number=None):
    """True if a results-file entry (name, optional number) is the bye."""
    if number and str(number).strip().casefold() == BYE_NUMBER.casefold():
        return True
    return (name or "").strip().casefold() in BYE_NAMES


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

    @property
    def is_rated(self):
        """Whether this game is evidence for the rating formula.

        A bye or forfeit is a result (it counts in the record) but not a game
        anybody played, so the formula must never see it. Two shapes reach us:
        a game against the bye (Baxter, and the corpus's "Bye" rows), and a
        forfeit between two real players recorded as a 50-0 game, which the
        corpus marks only by a zero score. A genuine game with a zero score is
        misread as a forfeit; that has always been so (it is the calculator's
        old rule) and no such game exists.
        """
        if self.opponent is BYE or self.opponent is None:
            return False
        return bool(self.score) and bool(self.opp_score)

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
        number=None,
        init_rating=0,
        init_rating_deviation=0.0,
        career_games=0,
        rated_games=None,
        is_unrated=False,
        last_played=None,
    ):
        self.name = name
        # The CoCo player number, when the source file carried one. None for
        # everything the Google Form produces, which is most of the corpus.
        self.number = canonical_player_number(number) if number else None
        # Two counts, deliberately different (PLAN_UNPLAYED_GAMES decision 4):
        # career_games is every game in the record, byes and forfeits
        # included, and is what people are shown; rated_games counts only
        # games the formula saw, and is the only count the formula reads (the
        # multiplier). A ratings file carries one number, so it seeds both.
        self.career_games = career_games
        self.rated_games = career_games if rated_games is None else rated_games
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

    @property
    def key(self):
        """The identity this player is filed under.

        A number when the file gave one, the name otherwise. Every dict that
        carries players across tournaments keys on this, so a number-bearing
        file keeps two same-named players apart while the name-keyed corpus
        behaves exactly as it always has.
        """
        return self.number or self.name

    @classmethod
    def new_unrated(cls, name, number=None):
        return cls(
            name=name,
            number=number,
            init_rating=UNRATED_INIT_RATING,
            init_rating_deviation=MAX_DEVIATION,
            last_played=datetime.today(),
            is_unrated=True,
        )

    def __str__(self):
        return self.name

    def tally_results(self):
        self.update_game_counts()
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

    def update_game_counts(self):
        """Add this tournament's games to both counts.

        This used to skip byes by comparing the opponent to the string
        "Zz Bye", which no Player ever equals, so every bye and forfeit was
        counted towards the multiplier. rated_games now leaves them out.
        """
        for game in self.games:
            if game.opponent is self:
                continue
            self.career_games += 1
            if game.is_rated:
                self.rated_games += 1

    def get_score_by_round(self, r):
        return self.games[r].score

    def get_opponent_by_round(self, r):
        return self.games[r].opponent

    def get_opponents(self):
        """Every real opponent: the bye is not one."""
        return [g.opponent for g in self.games if g.opponent is not BYE]

    def adjust_initial_deviation(self, tournament_date):
        try:
            c = 10
            # Never negative: a tournament dated before the player's last one
            # (a late addition to a milestone) would otherwise shrink their
            # deviation, or take the square root of a negative number.
            inactive_days = max(0, int((tournament_date - self.last_played).days))
            init = self.init_rating_deviation
            new = math.sqrt((init * init) + (c * c * inactive_days))
            self.init_rating_deviation = min(new, MAX_DEVIATION)
            if abs(init - self.init_rating_deviation) > 1e-5:
                logger.info(
                    "Adjusted rating deviation for %s: %f -> %f",
                    self.name,
                    init,
                    self.init_rating_deviation,
                )
        except Exception as ex:
            show_exception(ex)


# The opponent in every game against the bye. It is deliberately a Player, so
# the writers (which print ``g.opponent.name``) need no special case, but it is
# never added to a Section, a PlayerList or a RatingsDB: the bye is not a
# player, has no rating, and must not be carried from one tournament to the
# next. Never mutated.
BYE = Player("Bye")


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
