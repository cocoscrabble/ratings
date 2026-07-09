#!/usr/bin/python

# Run as
#   python scripts/simulation.py <beta>
#
# e.g.
#   python scripts/simulation.py 4
#
# will generate the file
#   complete-ratings-beta-4.0.csv

import sys

from coco_ratings.pipeline import run_simulation
from coco_ratings.reports import write_complete_ratings


def run_gui():
    from coco_ratings.gui_app import SimulationApp

    SimulationApp().mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        beta = float(sys.argv[1])
        pdb = run_simulation(beta)
        filename = f"complete-ratings-beta-{beta}.csv"
        write_complete_ratings(pdb, filename)
    else:
        run_gui()
