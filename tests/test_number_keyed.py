"""Results and ratings files may identify players by number as well as by name.

Two producers feed this engine and they disagree about what a player is. The
Google Form export knows only self-typed names; Baxter knows CoCo player
numbers. Both forms are valid input, dispatched on the header — see
plans/baxter-integration.md phase 2.

The cases that matter are the ones where the two forms meet: the same human
appearing first under a name and later under a number must stay one player with
one continuous career, and two humans sharing a name must not be merged just
because the older format could not tell them apart.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from coco_ratings.io import ParserError
from coco_ratings.players import PlayerDB
from coco_ratings.rating import PlayerList, Tournament
from coco_ratings.ratingsdb import RatingsDB

LEGACY_HEADER = "Submitted On,Round,Winner,Winners Score,Opponent,Opponents Score"
NUMBER_HEADER = LEGACY_HEADER + ",Winner Number,Opponent Number"


def _write(tmp: Path, name: str, text: str) -> str:
    p = tmp / name
    p.write_text(text)
    return str(p)


def _results(tmp, name, games, header=LEGACY_HEADER):
    """games: (round, winner, winner_score, opponent, opponent_score, *numbers)."""
    rows = [header]
    for rnd, w, ws, o, os_, *numbers in games:
        rows.append(",".join(str(x) for x in (f"2024-01-01,{rnd}", w, ws, o, os_, *numbers)))
    return _write(tmp, name, "\n".join(rows) + "\n")


def _ratings(tmp, name, players, header="Name,Rating,Email"):
    rows = [header] + [",".join(str(x) for x in row) for row in players]
    return _write(tmp, name, "\n".join(rows) + "\n")


class TmpDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.playerdb = PlayerDB([["alice", "1"], ["becky", "2"]])

    def _read(self, results, ratings=None, name="t", date=datetime(2024, 1, 1)):
        t = Tournament(ratings, results, name, date)
        t.calc_ratings(beta=5)
        return t


class HeaderDispatchTest(TmpDirTest):
    """Which form a file is in is decided once, from its header."""

    def test_legacy_header_keys_by_name(self):
        f = _results(self.tmp, "t-results.csv", [(1, "alice", 400, "becky", 300)])
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["alice", "becky"])
        for p in t.player_list.players.values():
            self.assertIsNone(p.number)

    def test_number_header_keys_by_number(self):
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300, "0001", "0002")],
            header=NUMBER_HEADER,
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["0001", "0002"])
        by_number = {p.number: p.name for p in t.player_list.players.values()}
        self.assertEqual(by_number, {"0001": "alice", "0002": "becky"})

    def test_numbers_are_canonicalized(self):
        # data/players.csv writes numbers bare; Baxter writes them padded. Both
        # spellings must land on one key, or one player becomes two.
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300, "1", "00002")],
            header=NUMBER_HEADER,
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["0001", "0002"])

    def test_half_a_number_header_is_refused(self):
        # A file carrying one number column is malformed. Resolving it row by
        # row would key some players by number and others by name, splitting
        # people in two without ever saying so.
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300, "0001")],
            header=LEGACY_HEADER + ",Winner Number",
        )
        with self.assertRaises(ParserError) as cm:
            self._read(f)
        self.assertIn("opponent number", str(cm.exception))

    def test_unrelated_extra_columns_stay_name_keyed(self):
        # Real files in results/ carry extra Form columns; they are not numbers.
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300, "first", "yes")],
            header=LEGACY_HEADER + ",Did the winner go first or second,Opponent Affirmation",
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["alice", "becky"])

    def test_bom_and_quoted_headers_are_still_detected(self):
        # Both appear throughout results/; neither may hide the number columns.
        quoted = ",".join(f'"{c}"' for c in NUMBER_HEADER.split(","))
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300, "0001", "0002")],
            header="﻿" + quoted,
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["0001", "0002"])

    def test_reader_reports_which_form_it_read(self):
        from coco_ratings.io import ResultCSVReader

        for header, expected in ((LEGACY_HEADER, "name"), (NUMBER_HEADER, "number")):
            games = [(1, "alice", 400, "becky", 300)]
            if expected == "number":
                games = [(1, "alice", 400, "becky", 300, "0001", "0002")]
            f = _results(self.tmp, "t-results.csv", games, header=header)
            reader = ResultCSVReader(PlayerList(None), "t", datetime(2024, 1, 1))
            reader.parse(f)
            self.assertEqual(reader.keyed_by, expected)


class SameNameTest(TmpDirTest):
    """The case the legacy format cannot express."""

    def test_two_players_sharing_a_name_stay_two_players(self):
        # Both are "alice"; only their numbers tell them apart. Under the
        # name-keyed reader they would be one player with twice the games.
        f = _results(
            self.tmp,
            "t-results.csv",
            [
                (1, "alice", 400, "becky", 300, "0001", "0002"),
                (2, "alice", 450, "becky", 300, "0003", "0002"),
            ],
            header=NUMBER_HEADER,
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["0001", "0002", "0003"])
        first, second = t.player_list.players["0001"], t.player_list.players["0003"]
        self.assertEqual(first.name, second.name)
        self.assertEqual(len(first.games), 1)
        self.assertEqual(len(second.games), 1)
        # becky played both of them.
        self.assertEqual(len(t.player_list.players["0002"].games), 2)

    def test_the_name_keyed_reader_merges_them(self):
        # The same file without its number columns: one "alice" with two games.
        # Pinned to show what the numbers are actually buying.
        f = _results(
            self.tmp,
            "t-results.csv",
            [(1, "alice", 400, "becky", 300), (2, "alice", 450, "becky", 300)],
        )
        t = self._read(f)
        self.assertEqual(sorted(t.player_list.players), ["alice", "becky"])
        self.assertEqual(len(t.player_list.players["alice"].games), 2)


class MixedFormTest(TmpDirTest):
    """The two halves of one tournament need not agree about the form."""

    def test_name_keyed_seed_is_adopted_by_a_number_keyed_result(self):
        # The ratings file is a Sheets export with no numbers to give; the
        # results come from Baxter and have them. Seeding a duplicate at
        # unrated would throw away the rating alice walked in with.
        ratings = _ratings(self.tmp, "t-ratings.csv", [("alice", 1600, ""), ("becky", 1500, "")])
        results = _results(
            self.tmp,
            "t-results.csv",
            [(r, "alice", 400, "becky", 300) + ("0001", "0002") for r in range(1, 6)],
            header=NUMBER_HEADER,
        )
        t = self._read(results, ratings)
        self.assertEqual(sorted(t.player_list.players), ["0001", "0002"])
        alice = t.player_list.players["0001"]
        self.assertEqual(alice.init_rating, 1600)
        self.assertFalse(alice.is_unrated)

    def test_number_bearing_ratings_file(self):
        ratings = _ratings(
            self.tmp,
            "t-ratings.csv",
            [("alice", 1600, "", "0001"), ("becky", 1500, "", "0002")],
            header="Name,Rating,Email,Number",
        )
        players = PlayerList(ratings).players
        self.assertEqual(sorted(players), ["0001", "0002"])
        self.assertEqual(players["0001"].init_rating, 1600)


class CarryForwardTest(TmpDirTest):
    """One human, two file formats, one continuous career."""

    def _replay(self, *tournaments):
        db = RatingsDB(self.playerdb, beta=5)
        for i, (ratings, results) in enumerate(tournaments, start=1):
            db.process_one_tournament(
                ratings, results, f"t{i}", datetime(2024, i, 1)
            )
        return db

    def _name_keyed(self, n):
        return _results(
            self.tmp,
            f"t{n}-results.csv",
            [(r, "alice", 400, "becky", 300) for r in range(1, 6)],
        )

    def _number_keyed(self, n):
        return _results(
            self.tmp,
            f"t{n}-results.csv",
            [(r, "alice", 400, "becky", 300, "0001", "0002") for r in range(1, 6)],
            header=NUMBER_HEADER,
        )

    def test_a_number_keyed_tournament_continues_a_name_keyed_career(self):
        # This is the migration case: the whole corpus is name-keyed, and the
        # first Baxter file must not reset everyone to unrated.
        db = self._replay((None, self._name_keyed(1)), (None, self._number_keyed(2)))
        self.assertEqual(sorted(db.players), ["0001", "0002"])
        self.assertEqual(db.players["0001"].name, "alice")
        # Ten games, not five: the career carried forward rather than restarting.
        self.assertEqual(db.players["0001"].games, 10)
        # And the history moved with it, rather than being stranded under the name.
        self.assertEqual(sorted(db.report["0001"]), ["t1", "t2"])

    def test_a_name_keyed_tournament_continues_a_number_keyed_career(self):
        # The reverse: Baxter runs an event, then the Google Form runs the next
        # one and knows only the name. The alias has to carry it back.
        db = self._replay((None, self._number_keyed(1)), (None, self._name_keyed(2)))
        self.assertEqual(sorted(db.players), ["0001", "0002"])
        self.assertEqual(db.players["0001"].games, 10)
        self.assertEqual(sorted(db.report["0001"]), ["t1", "t2"])

    def test_all_name_keyed_is_unchanged(self):
        db = self._replay((None, self._name_keyed(1)), (None, self._name_keyed(2)))
        self.assertEqual(sorted(db.players), ["alice", "becky"])
        self.assertEqual(db.players["alice"].games, 10)

    def test_the_replay_tallies_which_form_each_tournament_was_in(self):
        # build_db prints this, so the corpus's progress away from name-keying
        # is visible rather than something to go and count.
        db = self._replay(
            (None, self._name_keyed(1)),
            (None, self._number_keyed(2)),
            (None, self._name_keyed(3)),
        )
        self.assertEqual(dict(db.keyed_by), {"name": 2, "number": 1})

    def test_a_number_bearing_file_supplies_its_own_coco_id(self):
        # data/players.csv is the name->number join that exists only because
        # the Form cannot carry a number. When the file has one, use it — and
        # do not report the player as missing from players.csv.
        db = self._replay((None, self._number_keyed(1)))
        self.assertEqual(db.report["0001"]["t1"].coco_id, "0001")
        self.assertEqual(db.missing_ids, set())


if __name__ == "__main__":
    unittest.main()
