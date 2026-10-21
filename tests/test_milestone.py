"""Rating milestones: frozen history seeds the replay, exactly.

The guarantees, each pinned here:

- seeding from a milestone is bit-identical to replaying through it, so a
  milestone can be cut at any time without accumulating error;
- cutting can only add frozen history, never change it;
- a frozen results file may change only on the record, and then moves the
  record, never a rating;
- a tournament cannot slip in before the milestone unnoticed.

See plans/rating-milestones.md.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from coco_ratings import milestone as ms
from coco_ratings import pipeline
from coco_ratings.milestone import Milestone, MilestoneError
from coco_ratings.tournaments import TournamentDB, TournamentEntry
from coco_ratings.types import Player

from tests.test_golden import GOLDEN_CUTOFF


def replay(**kw):
    return pipeline.process_old_results(quiet=True, **kw)[0]


def snapshot(db):
    players = {k: vars(r) for k, r in db.players.items()}
    report = {
        (k, t): vars(r) for k, reps in db.report.items() for t, r in reps.items()
    }
    return players, report, dict(db.aliases)


def cut_points():
    """A few tournaments inside the golden prefix to cut at."""
    names = [
        e.filename for e in TournamentDB.read_csv().tournaments
        if e.filename and e.date <= GOLDEN_CUTOFF
    ]
    return [names[len(names) // 4], names[len(names) // 2], names[-3]]


def last_tournament():
    return [e.filename for e in TournamentDB.read_csv().tournaments if e.filename][-1]


class TmpMilestone(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name) / "milestone"

    def cut_at(self, name, previous=None):
        db = replay(milestone=previous, stop_after=name)
        ms.cut(self.dir, db, db.rated, pipeline.results_files(), previous=previous)
        return Milestone.load(self.dir)


class SeedingEquivalenceTest(TmpMilestone):
    """The guard against a piece of carried state nobody put in the milestone:
    if the replay ever carries something new, seeding stops reproducing it."""

    def test_seeding_reproduces_the_full_replay(self):
        full = snapshot(replay(milestone=None, until=GOLDEN_CUTOFF))
        for name in cut_points():
            with self.subTest(cut=name):
                m = self.cut_at(name)
                seeded = snapshot(replay(milestone=m, until=GOLDEN_CUTOFF))
                self.assertEqual(seeded[0], full[0])
                self.assertEqual(seeded[1], full[1])
                self.assertEqual(seeded[2], full[2])

    def test_seeding_reproduces_the_whole_history(self):
        # Through the end, not just the golden prefix: that is where the
        # number-keyed files are, whose players were filed by name before.
        full = snapshot(replay(milestone=None))
        m = self.cut_at(last_tournament())
        self.assertEqual(snapshot(replay(milestone=m)), full)

    def test_cutting_again_keeps_every_frozen_row(self):
        first, second = cut_points()[:2]
        m1 = self.cut_at(first)
        m2 = self.cut_at(second, previous=m1)
        for k, v in m1.history.items():
            self.assertEqual(m2.history[k], v)
        self.assertGreater(len(m2.history), len(m1.history))

    def test_cutting_refuses_to_change_frozen_history(self):
        first, second = cut_points()[:2]
        m1 = self.cut_at(first)
        k = next(iter(m1.history))
        m1.history[k] = dict(m1.history[k], new_rating=1)
        db = replay(milestone=None, stop_after=second)
        with self.assertRaises(MilestoneError):
            ms.cut(self.dir, db, db.rated, pipeline.results_files(), previous=m1)


class AmendmentTest(TmpMilestone):
    """A frozen file corrected later: the record moves, the ratings do not."""

    def setUp(self):
        super().setUp()
        results = Path(self._tmp.name) / "results"
        shutil.copytree(pipeline.RESULTS_DIR, results)
        patcher = mock.patch.object(pipeline, "RESULTS_DIR", results)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.results = results
        self.name = cut_points()[0]
        self.milestone = self.cut_at(self.name)
        self.before = replay(milestone=self.milestone, until=GOLDEN_CUTOFF)
        # A bye for someone in the frozen tournament, as a backfill would add.
        self.file = next(results.glob(f"{self.name}-results.?sv"))
        sep = "\t" if self.file.suffix == ".tsv" else ","
        first = self.file.read_text().splitlines()[1].split(sep)
        self.player = first[2]
        with open(self.file, "a") as f:
            f.write(sep.join(["", "99", self.player, "50", "Bye", "0"]) + "\n")

    def test_an_unrecorded_change_is_refused(self):
        with self.assertRaisesRegex(MilestoneError, "no recorded amendment"):
            replay(milestone=Milestone.load(self.dir))

    def test_a_recorded_change_moves_the_record_and_no_rating(self):
        manifest = json.loads((self.dir / "manifest.json").read_text())
        manifest["amendments"].append({
            "filename": self.name, "results_sha256": ms.sha256_of(self.file),
            "date": "2026-10-21", "reason": "test",
        })
        (self.dir / "manifest.json").write_text(json.dumps(manifest))
        after = replay(milestone=Milestone.load(self.dir), until=GOLDEN_CUTOFF)

        key = next(k for k, r in after.report.items()
                   if self.name in r and r[self.name].name == self.player)
        old, new = self.before.report[key][self.name], after.report[key][self.name]
        self.assertEqual(new.wins, old.wins + 1)
        self.assertEqual(new.spread, old.spread + 50)
        for k, reps in after.report.items():
            for t, r in reps.items():
                b = self.before.report[k][t]
                self.assertEqual(
                    (r.old_rating, r.new_rating, r.old_deviation, r.new_deviation),
                    (b.old_rating, b.new_rating, b.old_deviation, b.new_deviation),
                )


def entry(filename, date, order=""):
    return TournamentEntry("", "", "", "", "", filename, date, order)


class PlanTest(unittest.TestCase):
    """What may and may not change around frozen history (decision 5)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.files = {}
        for name in ("a", "b", "c"):
            p = Path(tmp.name) / f"{name}-results.csv"
            p.write_text(name)
            self.files[name] = str(p)
        self.m = Milestone(
            through="b",
            frozen=[{"filename": n, "results_sha256": ms.sha256_of(self.files[n])}
                    for n in ("a", "b")],
            history={}, state={}, aliases={},
        )
        self.entries = [entry("a", "2024-01-01"), entry("b", "2024-02-01"),
                        entry("c", "2024-03-01")]

    def test_the_rest_is_rated(self):
        frozen, rest = self.m.plan(self.entries, self.files)
        self.assertEqual([e.filename for e in frozen], ["a", "b"])
        self.assertEqual([e.filename for e in rest], ["c"])

    def test_a_frozen_tournament_cannot_disappear(self):
        with self.assertRaisesRegex(MilestoneError, "missing from tournaments.csv"):
            self.m.plan(self.entries[1:], self.files)

    def test_a_corrected_date_keeps_the_frozen_order(self):
        entries = [entry("a", "2024-02-15"), entry("b", "2024-02-01"),
                   entry("c", "2024-03-01")]
        frozen, _ = self.m.plan(sorted(entries, key=ms._sort_key), self.files)
        self.assertEqual([e.filename for e in frozen], ["a", "b"])

    def test_a_tournament_before_the_milestone_must_be_declared(self):
        entries = self.entries + [entry("old", "2023-06-01")]
        entries.sort(key=ms._sort_key)
        with self.assertRaisesRegex(MilestoneError, "late_additions"):
            self.m.plan(entries, self.files)
        self.m.late_additions = ["old"]
        _, rest = self.m.plan(entries, self.files)
        # Rated first, against the milestone's ratings.
        self.assertEqual([e.filename for e in rest], ["old", "c"])


class LateDeviationTest(unittest.TestCase):
    def test_playing_in_the_past_does_not_shrink_deviation(self):
        p = Player("x", init_rating=1500, init_rating_deviation=40,
                   last_played=datetime(2026, 1, 1))
        p.adjust_initial_deviation(datetime(2025, 1, 1))
        self.assertEqual(p.init_rating_deviation, 40)
