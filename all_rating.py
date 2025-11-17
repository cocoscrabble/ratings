"""Rate a sequence of tournaments.

Carries forward ratings and std deviation for repeat players. This is a stopgap
measure until we put an actual database in place.
"""

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime
import glob
import os
from io import StringIO
import sys
import tkinter as tk

from players import PlayerDB
import rating
from rating import Tournament, CSVResultWriter, TabularResultWriter
from tournaments import TournamentDB


# Used in simulations
_BETA = 5


@dataclass
class Player:
    name: str
    rating: float
    deviation: float
    games: int
    last_played: datetime

    @classmethod
    def from_tournament_player(cls, p):
        return cls(
            p.name, p.new_rating, p.new_rating_deviation, p.career_games, p.last_played
        )


@dataclass
class PlayerReport:
    name: str
    coco_id: str
    old_rating: float
    new_rating: float
    old_deviation: float
    new_deviation: float
    games: int

    @classmethod
    def from_tournament_player(cls, p, playerdb):
        try:
            coco_id = playerdb.get_id(p.name)
        except KeyError:
            print(f"MISSING NAME: {p.name}")
            coco_id = "9999"
        return cls(
            p.name,
            coco_id,
            p.init_rating,
            p.new_rating,
            round(p.init_rating_deviation, 2),
            round(p.new_rating_deviation, 2),
            p.career_games,
        )


class CSVRatingsFileWriter:
    """Write ratings in csv format.

    CSV format:
        name, rating, rating deviation
    """

    def headers(self):
        return ["Name", "Rating", "Deviation", "Games played"]

    def row(self, p):
        return [p.name, p.rating, p.deviation, p.games]

    def write_file(self, output_file, players):
        players = sorted(players, key=lambda p: -p.rating)
        with open(output_file, "w", newline="") as f:
            self.write(f, players)

    def write(self, f, players):
        writer = csv.writer(f)
        writer.writerow(self.headers())
        for p in players:
            writer.writerow(self.row(p))


class RatingsDB:
    """Ratings database."""

    def __init__(self, playerdb):
        self.playerdb = playerdb
        self.players = {}
        self.report = defaultdict(dict)

    def update(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                self.players[p.name] = Player.from_tournament_player(p)
                self.report[p.name][tournament.name] = (
                    PlayerReport.from_tournament_player(p, self.playerdb)
                )

    def adjust_tournament(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                if p.name not in self.players:
                    continue
                dbp = self.players[p.name]
                # if p.init_rating != dbp.rating:
                #     print(f"Adjusting: {p.name} : {p.init_rating} -> {dbp.rating}")
                p.init_rating = dbp.rating
                p.init_rating_deviation = dbp.deviation
                p.career_games += dbp.games
                p.is_unrated = False
                p.last_played = dbp.last_played
                p.adjust_initial_deviation(tournament.date)
                p.last_played = tournament.date

    def process_one_tournament(self, rat_file, res_file, name, date):
        t = Tournament(rat_file, res_file, name, date)
        self.adjust_tournament(t)
        t.calc_ratings(_BETA)
        self.update(t)
        return t


def show_file(f):
    f.seek(0)
    for line in f.readlines():
        print(line.strip())


def process_old_results(display_progress=False):
    d = os.path.join(os.path.dirname(__file__), "results")
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = PlayerDB.read_csv()
    tournamentdb = TournamentDB.read_csv()
    ratingsdb = RatingsDB(playerdb)
    for t in tournamentdb.tournaments:
        prefix, date = t.filename, t.date
        if not prefix:
            print(f"!! No results file for {t.fancy_name}")
            continue
        if display_progress:
            print(f"Reading {prefix}")
        date = datetime.strptime(date, "%Y-%m-%d")
        res = hres[prefix]
        rat = hrat[prefix]
        t = ratingsdb.process_one_tournament(rat, res, prefix, date)
    return ratingsdb, t


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


def write_report(filename, ratingsdb):
    fields = ("old_rating", "new_rating", "old_deviation", "new_deviation", "games")
    with open(filename, "w") as f:
        writer = csv.writer(f)
        header = [None, None] + [name for name, _ in ALL]
        writer.writerow(header)
        for p, rep in sorted(ratingsdb.report.items()):
            for x in fields:
                out = [p, x]
                for name, _ in ALL:
                    pl = rep.get(name)
                    entry = pl and getattr(pl, x)
                    out.append(entry)
                writer.writerow(out)


def write_latest_ratings(outfile, ratingsdb, t):
    # Display the most recent tournament
    print("-------------------------")
    print(f"Ratings adjustment for most recent tournament")
    res_out = StringIO("")
    TabularResultWriter().write(res_out, t)
    show_file(res_out)
    print("-------------------------")
    CSVResultWriter().write_file(outfile, t)
    # Also write out the complete rating list
    write_complete_ratings(ratingsdb)


def write_complete_ratings(ratingsdb, filename=None):
    if not filename:
        filename = "complete-ratings-list.csv"
    ps = ratingsdb.players.values()
    CSVRatingsFileWriter().write_file(filename, ps)
    print(f"Wrote all current ratings to {filename}")


def write_sim_report(filename):
    ratingsdb, t = process_old_results()
    write_report(filename, ratingsdb)
    return ratingsdb


# -----------------------------------------------------
# GUI


class App(rating.App):
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
        name = "Tournament name"
        tdate = datetime.today()
        write_current_ratings(outfile)
        self.set_status(f"Wrote ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")


class ReportApp(rating.App):
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
        name = "Tournament name"
        tdate = datetime.today()
        write_current_ratings(outfile)
        self.set_status(f"Wrote ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")


def run_simulation(beta=5):
    global _BETA
    _BETA = beta
    filename = f"run-with-beta-{beta}-report.csv"
    pdb = write_sim_report(filename)
    print(f"Wrote simulation report to {filename}")
    return pdb


class SimulationApp(rating.SimulationApp):
    def run_simulation(self):
        try:
            beta = int(self.beta_input.get())
        except ValueError:
            beta = 5
        run_simulation(beta)
        self.set_status(f"Wrote simulation report to {filename}")


def run_gui():
    w = App()
    w.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        write_current_ratings(filename)
    else:
        run_gui()
