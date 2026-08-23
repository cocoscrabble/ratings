"""Opt-in debug logging for the entry points.

The rating math logs generously — every game's per-player rating movement, which
is what makes ``scripts/rating_history.py`` archaeology possible. Deciding
whether anything *listens* to that is an entry point's job, never a library's.

``rating.py`` used to call ``logging.basicConfig`` at import time. That meant
merely importing the rating engine reconfigured the importer's root logger and
started writing a DEBUG file into whatever the working directory happened to be
— which is how this repo accumulated a 1.68 GB ``coco_ratings.log`` (and the
stray copies under ``web/`` and ``scripts/``). It also cost real time: the test
suite runs about 11x faster with the debug file handler off.

Call this from a ``main()``; do not call it from library code.
"""

import logging

LOG_FILE = "coco_ratings.log"


def configure_file_logging(path=LOG_FILE, level=logging.DEBUG):
    """Attach the debug file handler used by the CLI and the GUI."""
    logging.basicConfig(filename=path, encoding="utf-8", level=level)
