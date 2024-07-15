#!/usr/bin/python

# Run as
#   python rerate_all.py

import csv
from datetime import datetime
import glob
from io import StringIO
import os
import sys

import all_rating
import rating
from rating import Tournament, TabularResultWriter


class ResultWriter:
    """Write out tournament results."""

    def __init__(self):
        self.tournament = None

    def headers(self):
        return [
                'Name', 'Tournament', 'Old Rating', 'New Rating'
        ]

    def get_sorted_players(self, section):
        return sorted(section.get_players(),
                key=lambda x: (x.wins * 100000) + x.spread,
                reverse=True)

    def row(self, p):
        return [
                p.name, f'{self.tournament.name}',
                p.init_rating, p.new_rating
        ]


class CSVResultWriter(ResultWriter):
    """Write out results in .csv format."""

    def write_file(self, output_file, tournament):
        with open(output_file, 'w', newline='') as f:
            self.write(f, tournament)

    def write(self, f, tournament):
        self.tournament = tournament
        writer = csv.writer(f)
        for s in tournament.sections:
            self._write_section(writer, s)

    def _write_section(self, out, section):
        for p in self.get_sorted_players(section):
            out.writerow(self.row(p))


def process_results(f):
    d = os.path.join(os.path.dirname(__file__), "results")
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = all_rating.PlayerDB()
    for prefix, date in all_rating.ALL:
        print(f"Reading {prefix}")
        date = datetime.strptime(date, '%Y-%m-%d')
        res = hres[prefix]
        rat = hrat[prefix]
        t = playerdb.process_one_tournament(rat, res, prefix, date)
        res_out = StringIO('')
        TabularResultWriter().write(res_out, t)
        CSVResultWriter().write(f, t)
        all_rating.show_file(res_out)
        print("-------------------------")
    return playerdb, t


if __name__ == '__main__':
    with open("out.csv", "w") as f:
        process_results(f)
