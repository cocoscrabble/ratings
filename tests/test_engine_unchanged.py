"""Ratings published after the milestone must not move: the code is pinned.

Tournaments after the milestone are rated by the current code on every build,
and their ratings are published. So the code that rates them must stay the
code that published them. ``milestone/manifest.json`` records a fingerprint of
that code (``engine_sha256``, see ``milestone.engine_fingerprint``), and this
fails when the code no longer matches it.

Adding a tournament never fails here: it changes data, not code.

Changing the rating code fails here until a milestone records it. If nothing
has been rated since the milestone, nothing published can move, so just cut:

    uv run coco-rate milestone

Otherwise cut with the code as it was first (``coco-rate milestone`` refuses
to do it with the changed code), then cut again to record the change:

    git stash && uv run coco-rate milestone && git stash pop && uv run coco-rate milestone
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coco_ratings import milestone as ms
from coco_ratings import pipeline
from coco_ratings.milestone import Milestone, MilestoneError, engine_fingerprint
from coco_ratings.paths import MILESTONE_DIR


@unittest.skipUnless(
    (MILESTONE_DIR / "manifest.json").exists(), "no milestone committed"
)
class EngineUnchangedTest(unittest.TestCase):
    def test_rating_code_matches_the_milestone(self):
        m = Milestone.load(MILESTONE_DIR)
        if not pipeline.code_changed(m):
            return
        rated_since = pipeline.unfrozen_tournaments(m)
        if rated_since:
            self.fail(
                f"The rating code changed, and would re-rate {len(rated_since)} "
                f"published tournament(s) after the milestone "
                f"({', '.join(rated_since)}). Cut a milestone with the code as "
                f"it was, then cut again to record the change:\n"
                f"    git stash && uv run coco-rate milestone && git stash pop "
                f"&& uv run coco-rate milestone"
            )
        self.fail(
            "The rating code changed since the milestone recorded it. Nothing "
            "has been rated since the milestone, so nothing published moves: "
            "run `uv run coco-rate milestone` to record the new code."
        )


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pkg = Path(tmp.name) / "coco_ratings"
        shutil.copytree(Path(ms.__file__).parent, self.pkg,
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.base = engine_fingerprint(self.pkg)

    def test_editing_rating_code_changes_it(self):
        for rel in ("core/calculator.py", "io.py", "ratingsdb.py"):
            with self.subTest(rel=rel):
                path = self.pkg / rel
                original = path.read_bytes()
                path.write_bytes(original + b"\n# edit\n")
                self.assertNotEqual(engine_fingerprint(self.pkg), self.base)
                path.write_bytes(original)

    def test_a_new_module_counts(self):
        (self.pkg / "newthing.py").write_text("X = 1\n")
        self.assertNotEqual(engine_fingerprint(self.pkg), self.base)

    def test_output_and_ui_modules_do_not(self):
        for rel in sorted(ms.NOT_ENGINE):
            with self.subTest(rel=rel):
                path = self.pkg / rel
                original = path.read_bytes()
                path.write_bytes(original + b"\n# edit\n")
                self.assertEqual(engine_fingerprint(self.pkg), self.base)
                path.write_bytes(original)


@unittest.skipUnless(
    (MILESTONE_DIR / "manifest.json").exists(), "no milestone committed"
)
class CutGuardTest(unittest.TestCase):
    """``coco-rate milestone`` will not freeze published ratings as new code
    would rate them."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "milestone"
        shutil.copytree(MILESTONE_DIR, self.dir)

    def test_refused_when_code_changed_and_tournaments_rated_since(self):
        rated_since = ["some-later-tournament"]
        with mock.patch.object(pipeline, "code_changed", return_value=True), \
                mock.patch.object(pipeline, "unfrozen_tournaments",
                                  return_value=rated_since):
            with self.assertRaisesRegex(MilestoneError, "git stash"):
                pipeline.cut_milestone(directory=self.dir)

    def test_allowed_when_nothing_rated_since(self):
        with mock.patch.object(pipeline, "code_changed", return_value=True), \
                mock.patch.object(pipeline, "unfrozen_tournaments",
                                  return_value=[]):
            manifest = pipeline.cut_milestone(directory=self.dir)
        self.assertEqual(manifest["engine_sha256"], engine_fingerprint())

    def test_allowed_when_code_unchanged(self):
        with mock.patch.object(pipeline, "code_changed", return_value=False):
            manifest = pipeline.cut_milestone(directory=self.dir)
        self.assertEqual(manifest["engine_sha256"], engine_fingerprint())
