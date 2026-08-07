"""Golden-master test locking down the ratings computation.

A characterization test: it replays a *fixed* prefix of the tournament history
and compares a canonical snapshot of the result against a checked-in golden file.

The point is to catch changes to the rating *math*, so the input is pinned to
tournaments dated on or before GOLDEN_CUTOFF. Adding a new tournament therefore
does not touch this test — without the cutoff, every new result file changed the
numbers and the golden had to be regenerated, which is exactly what makes a
golden file stop meaning anything.

The snapshot is deliberately exhaustive: it records the final rating, deviation
and game count for every player, plus every player's before/after numbers for
every tournament they played in, so behaviour is pinned down game-by-game rather
than only at the final state.

Regenerate the golden file when a change to the numbers is *intentional*:

    UPDATE_GOLDEN=1 python -m unittest tests.test_golden

Two other things legitimately require regeneration, neither of them a bug in the
math: moving the cutoff, and back-filling a tournament dated on or before it
(that edits the pinned input). The rating math is also floating-point heavy, so
the values only reproduce on a matching Python/platform.
"""

import os
import unittest

from coco_ratings import pipeline as all_rating

# process_old_results() reads data/players.csv and data/tournaments.csv via
# paths relative to the current working directory, so the test must run from the
# repo root regardless of where the runner was invoked.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN_FILE = os.path.join(os.path.dirname(__file__), "golden_all_ratings.txt")

# Inclusive yyyy-mm-dd cutoff pinning the input. Covers 2021-09 through 2025-12
# (108 tournaments), which is more than enough history to exercise the math;
# everything after it is deliberately excluded so new tournaments can't break
# this test. Bumping this is a choice, not routine maintenance.
GOLDEN_CUTOFF = "2025-12-31"

# Tab-separated so player names containing commas can't corrupt the columns.
SEP = "\t"


def _fmt(value):
    return "" if value is None else str(value)


def _row(*values):
    return SEP.join(_fmt(v) for v in values)


def generate_snapshot():
    """Replay the pinned tournaments and render a canonical, sorted snapshot."""
    ratingsdb, _ = all_rating.process_old_results(until=GOLDEN_CUTOFF, quiet=True)

    lines = ["=== COMPLETE RATINGS LIST ===", _row("Name", "Rating", "Deviation", "Games")]
    for p in sorted(ratingsdb.players.values(), key=lambda p: (-p.rating, p.name)):
        lines.append(_row(p.name, p.rating, p.deviation, p.games))

    lines += [
        "",
        "=== PER-TOURNAMENT REPORT ===",
        _row(
            "Player", "Tournament", "CocoId",
            "OldRating", "NewRating", "OldDeviation", "NewDeviation", "Games",
        ),
    ]
    for name in sorted(ratingsdb.report):
        for tournament in sorted(ratingsdb.report[name]):
            r = ratingsdb.report[name][tournament]
            lines.append(
                _row(
                    name, tournament, r.coco_id,
                    r.old_rating, r.new_rating,
                    r.old_deviation, r.new_deviation, r.games,
                )
            )

    return "\n".join(lines) + "\n"


@unittest.skipIf(
    os.environ.get("SKIP_GOLDEN"),
    "SKIP_GOLDEN set: golden values are only reproducible on a matching "
    "Python/platform, so CI doesn't run this.",
)
class GoldenRatingsTest(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(REPO_ROOT)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_regenerated_ratings_match_golden(self):
        actual = generate_snapshot()

        if os.environ.get("UPDATE_GOLDEN"):
            with open(GOLDEN_FILE, "w") as f:
                f.write(actual)
            self.skipTest(f"Regenerated golden file at {GOLDEN_FILE}")

        with open(GOLDEN_FILE) as f:
            expected = f.read()

        self.assertMultiLineEqual(
            actual,
            expected,
            msg=(
                "Regenerated ratings differ from the golden file. If this change "
                "is intentional, regenerate it with:\n"
                "    UPDATE_GOLDEN=1 python -m unittest tests.test_golden"
            ),
        )


if __name__ == "__main__":
    unittest.main()
