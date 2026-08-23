"""Backwards-compatible re-export of the core data model.

The model moved to :mod:`coco_ratings.core.types` when the dependency-free core
was split out, this shim is so existing code importing it remains unchanged.
"""

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
    "Section",
    "show_exception",
]
