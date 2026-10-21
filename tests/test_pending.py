"""Ratings already published after the milestone must not move.

The milestone freezes history up to a point; tournaments after it are rated
by the current code on every build. Those are published too, so a code change
that re-rates them is the churn milestones exist to stop. This pins them:
``milestone/pending.csv`` holds the ratings of every tournament after the
milestone, and the build must reproduce them.

- **A new tournament** adds rows. Regenerate:
      UPDATE_PENDING=1 uv run python -m unittest tests.test_pending
- **A change to existing rows** means the code now rates published
  tournaments differently. Do not regenerate. Cut a milestone with the code
  as it was (``coco-rate milestone`` on main, before the change), which
  freezes them and empties this file, then land the change.

Unlike the golden test this runs in CI: the rows are few, and every one of
them has to survive any change that reaches production.
"""

import csv
import io
import os
import unittest

from coco_ratings import pipeline
from coco_ratings.milestone import HISTORY_FIELDS, Milestone
from coco_ratings.paths import MILESTONE_DIR

PENDING = MILESTONE_DIR / "pending.csv"


def pending_rows():
    """{(tournament, key): row} for every rated tournament after the milestone."""
    db, _ = pipeline.process_old_results(quiet=True)
    frozen = set(Milestone.load(MILESTONE_DIR).frozen_filenames)
    rows = {}
    for key, reports in db.report.items():
        for tournament, r in reports.items():
            if tournament not in frozen:
                rows[(tournament, key)] = [
                    tournament, key, repr(r.old_rating), repr(r.new_rating),
                    repr(r.old_deviation), repr(r.new_deviation),
                ]
    order = {name: i for i, name in enumerate(db.rated)}
    return dict(sorted(rows.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])))


def render(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HISTORY_FIELDS)
    w.writerows(rows.values())
    return buf.getvalue()


def read_expected():
    with open(PENDING, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        return {(r[0], r[1]): r for r in reader}


@unittest.skipUnless(
    (MILESTONE_DIR / "manifest.json").exists(), "no milestone committed"
)
class PendingRatingsTest(unittest.TestCase):
    def test_published_ratings_after_the_milestone_are_unchanged(self):
        actual = pending_rows()
        if os.environ.get("UPDATE_PENDING"):
            PENDING.write_text(render(actual))
            self.skipTest(f"Regenerated {PENDING}")
        expected = read_expected()
        changed = sorted(k for k in expected if actual.get(k) != expected[k])
        self.assertEqual(
            changed, [],
            "Published ratings after the milestone would change. Cut a "
            "milestone with the code as it was before this change "
            "(`coco-rate milestone` on main), then land the change. See "
            "tests/test_pending.py.",
        )
        added = sorted(set(actual) - set(expected))
        self.assertEqual(
            added, [],
            "New tournaments rated since pending.csv was written. Regenerate "
            "it: UPDATE_PENDING=1 uv run python -m unittest tests.test_pending",
        )
