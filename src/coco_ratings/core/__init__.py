"""The dependency-free heart of the rating system.

Everything in this subpackage imports nothing but the standard library and its
own siblings. That is the contract: it is what lets another application (Baxter,
the tournament manager) import the *same* rating math the official replay uses,
rather than reimplementing it and slowly disagreeing with it.

Two things therefore do not belong in here, ever: the file-format layer
(``coco_ratings.io``) and any logging configuration. ``tests/test_core_isolation.py``
enforces the first mechanically.
"""

from coco_ratings.core.calculator import RatingsCalculator
from coco_ratings.core.types import (
    MAX_DEVIATION,
    UNRATED_INIT_RATING,
    GameResult,
    Player,
    Section,
    show_exception,
)

__all__ = [
    "MAX_DEVIATION",
    "UNRATED_INIT_RATING",
    "GameResult",
    "Player",
    "RatingsCalculator",
    "Section",
    "show_exception",
]
