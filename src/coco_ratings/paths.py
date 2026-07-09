"""Filesystem anchors for the project's data files.

The package lives in ``src/coco_ratings/`` but the data it reads (``data/`` and
``results/``) lives at the project root, alongside ``pyproject.toml``. Resolving
these relative to this file (rather than the current working directory) means
the pipeline works regardless of where it is invoked from.
"""

import os
from pathlib import Path

# .../src/coco_ratings/paths.py -> parents[2] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Env overrides let a deployment point at explicit paths rather than relying on
# the install layout (e.g. a container where the package isn't editable-installed
# at the repo root). Unset -> same repo-relative defaults as always.
DATA_DIR = Path(os.environ.get("COCO_DATA_DIR") or PROJECT_ROOT / "data")
RESULTS_DIR = Path(os.environ.get("COCO_RESULTS_DIR") or PROJECT_ROOT / "results")

PLAYERS_CSV = DATA_DIR / "players.csv"
TOURNAMENTS_CSV = DATA_DIR / "tournaments.csv"
