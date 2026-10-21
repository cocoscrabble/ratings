"""Command-line / GUI entry point.

``coco-rate <output.txt>`` replays the tournament history (from the committed
milestone) and writes the current combined ratings list.
``coco-rate milestone [FILENAME]`` cuts a new rating milestone through that
tournament (default: the latest). With no argument it launches the Tk GUI.
"""

import sys

from coco_ratings.logging_setup import configure_file_logging
from coco_ratings.pipeline import write_current_ratings


def run_gui():
    # Imported lazily so the headless path (`coco-rate <file>`) never loads Tk.
    from coco_ratings.gui_app import App

    App().mainloop()


def main(argv=None):
    # Entry points own logging configuration; importing the engine must not
    # touch it (see coco_ratings.logging_setup).
    configure_file_logging()
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "milestone":
        from coco_ratings.pipeline import cut_milestone

        manifest = cut_milestone(argv[1] if len(argv) > 1 else None)
        print(
            f"Cut a milestone through {manifest['through']}: "
            f"{len(manifest['frozen'])} tournaments frozen."
        )
    elif argv:
        write_current_ratings(argv[0])
    else:
        run_gui()


if __name__ == "__main__":
    main()
