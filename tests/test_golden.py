"""Golden-master test locking down the full ratings-regeneration output.

This is a characterization test for the upcoming refactor: it replays the entire
tournament history (exactly what `all_rating` does when it rebuilds the ratings)
and compares a canonical snapshot of the result against a checked-in golden file.

Any change to the numbers a refactor produces will fail this test. If a change
is *intentional*, regenerate the golden file:

    UPDATE_GOLDEN=1 python -m unittest tests.test_golden

The snapshot is deliberately exhaustive: it records the final rating, deviation
and game count for every player, plus every player's before/after numbers for
every tournament they played in, so behaviour is pinned down game-by-game rather
than only at the final state.

Note: the rating math is floating-point heavy, so the golden values are only
guaranteed reproducible on a matching Python/platform; regenerate if you move
environments.
"""

import os
import unittest

from coco_ratings import pipeline as all_rating

# process_old_results() reads data/players.csv and data/tournaments.csv via
# paths relative to the current working directory, so the test must run from the
# repo root regardless of where the runner was invoked.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN_FILE = os.path.join(os.path.dirname(__file__), "golden_all_ratings.txt")

# Tab-separated so player names containing commas can't corrupt the columns.
SEP = "\t"


def _fmt(value):
    return "" if value is None else str(value)


def _row(*values):
    return SEP.join(_fmt(v) for v in values)


def generate_snapshot():
    """Replay every tournament and render a canonical, sorted text snapshot."""
    ratingsdb, _ = all_rating.process_old_results()

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
