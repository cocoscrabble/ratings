"""GUI applications that wire the Tk widgets to the history replay.

Kept separate from ``pipeline`` so the headless code path (the web `build_db`
command, `coco-rate <file>`) never imports tkinter. Only `cli.run_gui` and the
simulation script import this, and only when actually launching a window.
"""

from datetime import datetime

from coco_ratings import gui
from coco_ratings.io import CSVResultWriter
from coco_ratings.pipeline import (
    process_all_results,
    run_simulation,
    write_current_ratings,
)
from coco_ratings.reports import write_complete_ratings


class App(gui.App):
    def calculate_ratings(self):
        rating_file, result_file, outfile = self.files.get_files()
        if not (rating_file and result_file and outfile):
            self.set_status("Some filenames are not set")
            return
        name = "Tournament name"
        tdate = datetime.today()
        ratingsdb, t = process_all_results(rating_file, result_file, name, tdate)
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")
        # Also write out the complete rating list
        write_complete_ratings(ratingsdb)

    def recalculate_ratings(self):
        outfile = "latest_ratings.txt"
        write_current_ratings(outfile)
        self.set_status(f"Wrote ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")


class ReportApp(gui.App):
    def calculate_ratings(self):
        rating_file, result_file, outfile = self.files.get_files()
        if not (rating_file and result_file and outfile):
            self.set_status("Some filenames are not set")
            return
        name = "Tournament name"
        tdate = datetime.today()
        ratingsdb, t = process_all_results(rating_file, result_file, name, tdate)
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")
        # Also write out the complete rating list
        write_complete_ratings(ratingsdb)

    def recalculate_ratings(self):
        outfile = "latest_ratings.txt"
        write_current_ratings(outfile)
        self.set_status(f"Wrote ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")


class SimulationApp(gui.SimulationApp):
    def run_simulation(self):
        try:
            beta = int(self.beta_input.get())
        except ValueError:
            beta = 5
        run_simulation(beta)
        self.set_status(f"Wrote simulation report to run-with-beta-{beta}-report.csv")
