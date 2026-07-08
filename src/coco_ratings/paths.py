"""Filesystem anchors for the project's data files.

The package lives in ``src/coco_ratings/`` but the data it reads (``data/`` and
``results/``) lives at the project root, alongside ``pyproject.toml``. Resolving
these relative to this file (rather than the current working directory) means
the pipeline works regardless of where it is invoked from.
"""

from pathlib import Path

# .../src/coco_ratings/paths.py -> parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

PLAYERS_CSV = DATA_DIR / "players.csv"
TOURNAMENTS_CSV = DATA_DIR / "tournaments.csv"
