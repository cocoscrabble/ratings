#!/usr/bin/python

# Run as
#   python simulation.py <beta>
#
# e.g.
#   python simulation.py 4
#
# will generate the file
#   run-with-beta-4.0-report.csv

import sys

import all_rating


def run_gui():
    w = all_rating.SimulationApp()
    w.mainloop()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        beta = float(sys.argv[1])
        all_rating.run_simulation(beta)
    else:
        run_gui()
