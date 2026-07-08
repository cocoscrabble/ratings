#!/usr/bin/python

# Run as
#   python scripts/rerate_all.py
#
# Replays every tournament in chronological order and writes a per-tournament
# "old rating -> new rating" history for every player to out.csv.

import csv
from datetime import datetime
import glob
import os
from io import StringIO

from coco_ratings import pipeline
from coco_ratings.io import TabularResultWriter
from coco_ratings.paths import RESULTS_DIR
from coco_ratings.tournaments import TournamentDB


class CSVResultWriter:
    """Write per-tournament (name, tournament, old rating, new rating) rows."""

    def get_sorted_players(self, section):
        return sorted(
            section.get_players(),
            key=lambda x: (x.wins * 100000) + x.spread,
            reverse=True,
        )

    def row(self, p, tournament_name):
        return [p.name, tournament_name, p.init_rating, p.new_rating]

    def write(self, f, tournament):
        writer = csv.writer(f)
        for s in tournament.sections:
            for p in self.get_sorted_players(s):
                writer.writerow(self.row(p, tournament.name))


def process_results(f):
    d = str(RESULTS_DIR)
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(x)[:-12]: x for x in results}
    hrat = {os.path.basename(x)[:-12]: x for x in ratings}
    playerdb = pipeline.PlayerDB.read_csv()
    tournamentdb = TournamentDB.read_csv()
    ratingsdb = pipeline.RatingsDB(playerdb)
    writer = CSVResultWriter()
    latest = None
    for entry in tournamentdb.tournaments:
        prefix, date = entry.filename, entry.date
        if not prefix:
            print(f"!! No results file for {entry.fancy_name}")
            continue
        print(f"Reading {prefix}")
        date = datetime.strptime(date, "%Y-%m-%d")
        t = ratingsdb.process_one_tournament(hrat[prefix], hres[prefix], prefix, date)
        res_out = StringIO("")
        TabularResultWriter().write(res_out, t)
        writer.write(f, t)
        pipeline.show_file(res_out)
        latest = t
        print("-------------------------")
    return ratingsdb, latest


if __name__ == "__main__":
    with open("out.csv", "w") as f:
        process_results(f)
