"""Byes and forfeits: in the record, never in the rating formula.

A bye is a win and a forfeit a loss for every purpose except the rating
formula, which must never see either. The bye is not a player: it is in no
section, has no rating, and is not carried between tournaments. See
../baxter/plans/PLAN_UNPLAYED_GAMES.md.
"""

from datetime import datetime

from coco_ratings.io import ParserError
from coco_ratings.ratingsdb import RatingsDB
from coco_ratings.players import PlayerDB
from coco_ratings.rating import Tournament
from coco_ratings.types import BYE, Player, GameResult

from tests.test_number_keyed import NUMBER_HEADER, TmpDirTest, _ratings, _results

GAMES = [
    (1, "alice", 400, "becky", 350),
    (1, "carol", 420, "dave", 300),
    (2, "alice", 380, "carol", 390),
    (2, "becky", 410, "dave", 360),
]
RATINGS = [("alice", 1600, ""), ("becky", 1500, ""), ("carol", 1700, ""), ("dave", 1400, "")]


class ByeRowTest(TmpDirTest):
    def _rate(self, games, header=None):
        kw = {"header": header} if header else {}
        res = _results(self.tmp, "t-results.csv", games, **kw)
        rat = _ratings(self.tmp, "t-ratings.csv", RATINGS)
        return self._read(res, rat)

    def _player(self, t, name):
        return next(p for s in t.sections for p in s.players if p.name == name)

    def test_a_bye_is_a_win_in_the_record_and_absent_from_the_rating(self):
        plain = self._rate(GAMES)
        with_bye = self._rate(GAMES + [(3, "alice", 50, "Bye", 0)])
        alice = self._player(with_bye, "alice")
        self.assertEqual((alice.wins, alice.losses), (2, 1))
        self.assertEqual(alice.spread, self._player(plain, "alice").spread + 50)
        for name in ("alice", "becky", "carol", "dave"):
            self.assertEqual(
                self._player(with_bye, name).new_rating,
                self._player(plain, name).new_rating,
            )

    def test_the_bye_is_in_no_section(self):
        t = self._rate(GAMES + [(3, "alice", 50, "Bye", 0)])
        names = [p.name for s in t.sections for p in s.players]
        self.assertNotIn("Bye", names)
        self.assertNotIn("Bye", t.player_list.players)

    def test_a_forfeit_to_the_bye_is_a_loss(self):
        t = self._rate(GAMES + [(3, "Bye", 50, "dave", 0)])
        dave = self._player(t, "dave")
        self.assertEqual((dave.wins, dave.losses), (0, 3))
        self.assertEqual(dave.games[-1].opponent, BYE)

    def test_an_absence_scored_nil_nil_is_a_tie(self):
        t = self._rate(GAMES + [(3, "carol", 0, "Bye", 0)])
        carol = self._player(t, "carol")
        self.assertEqual((carol.wins, carol.losses), (2.5, 0.5))

    def test_baxters_numbered_bye_is_recognised_by_its_number(self):
        games = [g + (n1, n2) for g, (n1, n2) in zip(GAMES, [(1, 2), (3, 4), (1, 3), (2, 4)])]
        games.append((3, "Bye", 50, "dave", 0, "BYE", 4))
        res = _results(self.tmp, "t-results.csv", games, header=NUMBER_HEADER)
        db = RatingsDB(PlayerDB([]))
        db.process_one_tournament(None, res, "t", datetime(2024, 1, 1))
        self.assertNotIn("BYE", db.players)
        self.assertNotIn("Bye", db.players)
        self.assertEqual(len(db.players), 4)

    def test_both_sides_the_bye_is_refused(self):
        res = _results(self.tmp, "t-results.csv", GAMES + [(3, "Bye", 50, "Bye", 0)])
        with self.assertRaises(ParserError):
            Tournament(None, res, "t", datetime(2024, 1, 1))


class IsRatedTest(TmpDirTest):
    def test_a_real_game_is_rated(self):
        self.assertTrue(GameResult(1, Player("b"), 400, 350).is_rated)

    def test_a_game_against_the_bye_is_not(self):
        self.assertFalse(GameResult(1, BYE, 50, 0).is_rated)
        self.assertFalse(GameResult(1, BYE, 0, 50).is_rated)

    def test_a_forfeit_between_real_players_is_not(self):
        # The corpus records these as an ordinary 50-0 game
        # (wgpo-earlybird-2022); the zero is the only marker.
        self.assertFalse(GameResult(1, Player("b"), 50, 0).is_rated)
