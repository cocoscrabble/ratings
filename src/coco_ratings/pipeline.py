"""Rate a sequence of tournaments.

Carries forward ratings and std deviation for repeat players. This is a stopgap
measure until we put an actual database in place.
"""

from datetime import datetime
import glob
import os
from io import StringIO

from coco_ratings import gui
from coco_ratings.io import CSVResultWriter, TabularResultWriter
from coco_ratings.paths import RESULTS_DIR
from coco_ratings.players import PlayerDB
from coco_ratings.ratingsdb import RatingsDB
from coco_ratings.reports import (
    show_file,
    write_complete_ratings,
    write_latest_ratings,
    write_report,
)
from coco_ratings.tournaments import TournamentDB


def process_old_results(display_progress=False, beta: float = 5):
    d = str(RESULTS_DIR)
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = PlayerDB.read_csv()
    tournamentdb = TournamentDB.read_csv()
    ratingsdb = RatingsDB(playerdb, beta)
    latest = None
    for entry in tournamentdb.tournaments:
        prefix, date = entry.filename, entry.date
        if not prefix:
            print(f"!! No results file for {entry.fancy_name}")
            continue
        if display_progress:
            print(f"Reading {prefix}")
        date = datetime.strptime(date, "%Y-%m-%d")
        res = hres[prefix]
        rat = hrat[prefix]
        latest = ratingsdb.process_one_tournament(rat, res, prefix, date)
    if latest is None:
        raise RuntimeError("No tournaments with result files were processed")
    return ratingsdb, latest


def process_all_results(rating_file, result_file, name, tdate):
    ratingsdb, _ = process_old_results()
    # Now process the new tournament
    t = ratingsdb.process_one_tournament(rating_file, result_file, name, tdate)
    res_out = StringIO("")
    TabularResultWriter().write(res_out, t)
    show_file(res_out)
    print("-------------------------")
    return ratingsdb, t


def write_current_ratings(filename):
    ratingsdb, t = process_old_results()
    write_latest_ratings(filename, ratingsdb, t)


def write_sim_report(filename, beta: float = 5):
    ratingsdb, _ = process_old_results(beta=beta)
    write_report(filename, ratingsdb)
    return ratingsdb


# -----------------------------------------------------
# GUI


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


def run_simulation(beta: float = 5):
    filename = f"run-with-beta-{beta}-report.csv"
    pdb = write_sim_report(filename, beta)
    print(f"Wrote simulation report to {filename}")
    return pdb


class SimulationApp(gui.SimulationApp):
    def run_simulation(self):
        try:
            beta = int(self.beta_input.get())
        except ValueError:
            beta = 5
        run_simulation(beta)
        self.set_status(f"Wrote simulation report to run-with-beta-{beta}-report.csv")


