"""Command-line / GUI entry point.

``coco-rate <output.txt>`` replays the whole tournament history and writes the
current combined ratings list; with no argument it launches the Tk GUI.
"""

import sys

from coco_ratings.pipeline import write_current_ratings


def run_gui():
    # Imported lazily so the headless path (`coco-rate <file>`) never loads Tk.
    from coco_ratings.gui_app import App

    App().mainloop()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        write_current_ratings(argv[0])
    else:
        run_gui()


if __name__ == "__main__":
    main()
