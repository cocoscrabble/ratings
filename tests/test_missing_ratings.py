"""The per-tournament ratings file is optional.

Returning players are rated from the accumulated carry-forward ratings, so a
tournament's ratings file is redundant for them and dropping it is a no-op.
First-timers, whose seed the file would otherwise provide, fall back to being
rated as unrated from their own results. Nothing should crash when the file is
absent (see pipeline.process_old_results, which passes ratings_file=None).
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from coco_ratings.players import PlayerDB
from coco_ratings.rating import PlayerList, Tournament
from coco_ratings.ratingsdb import RatingsDB

RESULTS_HEADER = "Submitted On,Round,Winner,Winners Score,Opponent,Opponents Score\n"


def _write(tmp: Path, name: str, text: str) -> str:
    p = tmp / name
    p.write_text(text)
    return str(p)


def _results(tmp: Path, name: str, games) -> str:
    rows = RESULTS_HEADER + "".join(
        f"2024-01-01,{rnd},{w},{ws},{o},{os_}\n" for rnd, w, ws, o, os_ in games
    )
    return _write(tmp, name, rows)


def _ratings(tmp: Path, name: str, players) -> str:
    rows = "Name,Rating,Email\n" + "".join(f"{n},{r},\n" for n, r in players)
    return _write(tmp, name, rows)


class MissingRatingsFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.playerdb = PlayerDB([["alice", "1"], ["becky", "2"]])
        # Tournament 1: both players rated via a ratings file.
        self.t1_ratings = _ratings(self.tmp, "t1-ratings.csv", [("alice", 1600), ("becky", 1500)])
        self.t1_results = _results(
            self.tmp,
            "t1-results.csv",
            [(r, "alice", 400, "becky", 300) for r in range(1, 6)],
        )
        # Tournament 2: the same two players, both returning.
        self.t2_results = _results(
            self.tmp,
            "t2-results.csv",
            [(r, "becky", 450, "alice", 300) for r in range(1, 6)],
        )
        # A ratings file for T2 with *stale* numbers, to prove it is ignored.
        self.t2_ratings_stale = _ratings(
            self.tmp, "t2-ratings.csv", [("alice", 9999), ("becky", 1)]
        )

    def _replay(self, t2_ratings):
        db = RatingsDB(self.playerdb, beta=5)
        db.process_one_tournament(
            self.t1_ratings, self.t1_results, "t1", datetime(2024, 1, 1)
        )
        db.process_one_tournament(
            t2_ratings, self.t2_results, "t2", datetime(2024, 2, 1)
        )
        return {n: r.rating for n, r in db.players.items()}

    def test_playerlist_accepts_none(self):
        self.assertEqual(PlayerList(None).players, {})

    def test_tournament_builds_without_ratings_file(self):
        # Building and rating a tournament with no ratings file must not crash;
        # every player from the results is present and gets rated.
        t = Tournament(None, self.t2_results, "t2", datetime(2024, 2, 1))
        t.calc_ratings(beta=5)
        names = {p.name for s in t.sections for p in s.get_players()}
        self.assertEqual(names, {"alice", "becky"})

    def test_returning_players_ratings_file_is_a_noop(self):
        # Dropping T2's ratings file must yield identical ratings, and the stale
        # file's numbers must be ignored (carry-forward wins either way).
        with_file = self._replay(self.t2_ratings_stale)
        without_file = self._replay(None)
        self.assertEqual(with_file, without_file)
        # Sanity: ratings actually moved from their T1 values, so the assertion
        # above isn't trivially comparing untouched seeds.
        self.assertNotEqual(without_file["alice"], 1600)

    def _replay_with_newcomer(self, t2_ratings):
        # T2 adds a first-timer (carol) alongside returning alice/becky.
        results = _results(
            self.tmp,
            "t2n-results.csv",
            [
                (1, "carol", 500, "alice", 300),
                (2, "carol", 500, "becky", 300),
                (3, "alice", 400, "becky", 350),
                (4, "carol", 450, "alice", 400),
                (5, "becky", 400, "carol", 380),
            ],
        )
        db = RatingsDB(self.playerdb, beta=5)
        db.process_one_tournament(
            self.t1_ratings, self.t1_results, "t1", datetime(2024, 1, 1)
        )
        db.process_one_tournament(t2_ratings, results, "t2", datetime(2024, 2, 1))
        return {n: r.rating for n, r in db.players.items()}

    def test_ratings_file_with_only_new_players(self):
        # The only non-redundant entries a ratings file carries are seeds for
        # first-timers. A file listing *only* the newcomer must therefore work
        # and match a full file (returning players come from carry-forward).
        only_new = _ratings(self.tmp, "t2n-new.csv", [("carol", 1400)])
        full = _ratings(
            self.tmp,
            "t2n-full.csv",
            [("alice", 9999), ("becky", 1), ("carol", 1400)],  # alice/becky stale
        )
        from_only_new = self._replay_with_newcomer(only_new)
        from_full = self._replay_with_newcomer(full)
        self.assertEqual(from_only_new, from_full)
        self.assertIn("carol", from_only_new)
        # And carol's seed came from the file (1400), not the unrated default:
        # dropping her from the file entirely reseeds her from results, moving
        # every rating, so the minimal file is genuinely doing its job.
        from_empty = self._replay_with_newcomer(None)
        self.assertNotEqual(from_only_new["carol"], from_empty["carol"])


if __name__ == "__main__":
    unittest.main()
