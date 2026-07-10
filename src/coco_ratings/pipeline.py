"""Rate a sequence of tournaments.

Carries forward ratings and std deviation for repeat players. This is a stopgap
measure until we put an actual database in place.
"""

from datetime import datetime
import glob
import os
from io import StringIO

from coco_ratings.io import TabularResultWriter
from coco_ratings.paths import RESULTS_DIR
from coco_ratings.players import PlayerDB
from coco_ratings.ratingsdb import RatingsDB
from coco_ratings.reports import (
    show_file,
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
        res = hres.get(prefix)
        if res is None:
            # Can't rate a tournament with no results; skip it loudly.
            print(f"!! No results file for {prefix}, skipping")
            continue
        # The ratings file is optional: returning players are rated from the
        # accumulated carry-forward ratings, and first-timers are seeded from
        # their results. A missing file only affects genuine first-timers.
        rat = hrat.get(prefix)
        if rat is None:
            print(f"!! No ratings file for {prefix}, rating from accumulated ratings")
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


def run_simulation(beta: float = 5):
    filename = f"run-with-beta-{beta}-report.csv"
    pdb = write_sim_report(filename, beta)
    print(f"Wrote simulation report to {filename}")
    return pdb
