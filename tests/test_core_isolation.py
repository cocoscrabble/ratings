"""The core must stay importable on its own.

``coco_ratings.core`` is imported by Baxter (the tournament manager) to project
live in-tournament ratings using this project's own math rather than a second
implementation of it. That only works while the core keeps two properties:

1. importing it does not drag in the file-format layer, and
2. importing it does not configure logging.

Both were false before the core was split out, and both are the kind of thing a
stray convenience import silently undoes. See ``plans/baxter-integration.md``.
"""

import subprocess
import sys
import unittest


def _run(code):
    """Run ``code`` in a clean interpreter; return its stdout, asserting success."""
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise AssertionError(f"subprocess failed:\n{proc.stderr}")
    return proc.stdout.strip()


class CoreIsolationTest(unittest.TestCase):
    def test_core_import_does_not_pull_in_io(self):
        loaded = _run(
            "import coco_ratings.core, sys;"
            "print(','.join(sorted(m for m in sys.modules"
            " if m.startswith('coco_ratings'))))"
        )
        modules = set(loaded.split(","))
        self.assertNotIn("coco_ratings.io", modules)
        self.assertNotIn("coco_ratings.rating", modules)
        self.assertNotIn("coco_ratings.pipeline", modules)

    def test_core_import_does_not_configure_logging(self):
        # A library that calls basicConfig() installs a root handler on import,
        # hijacking the configuration of whatever imported it.
        handlers = _run(
            "import logging;"
            "import coco_ratings.core;"
            "print(len(logging.getLogger().handlers))"
        )
        self.assertEqual(handlers, "0")

    def test_core_import_writes_no_log_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [sys.executable, "-c", "import coco_ratings.core"],
                cwd=tmp, capture_output=True, text=True, check=True,
            )
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_public_surface(self):
        import coco_ratings.core as core

        for name in ("Player", "Section", "GameResult", "RatingsCalculator"):
            self.assertTrue(hasattr(core, name), f"core should export {name}")

    def test_types_shim_is_the_same_objects(self):
        # io, ratingsdb, the GUI and the older tests import from coco_ratings.types.
        # It must alias the core, not shadow it with a second class object.
        from coco_ratings import types
        from coco_ratings.core import types as core_types

        self.assertIs(types.Player, core_types.Player)
        self.assertIs(types.Section, core_types.Section)
        self.assertIs(types.GameResult, core_types.GameResult)
