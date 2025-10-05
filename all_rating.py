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

import rating
from rating import Tournament, CSVResultWriter, TabularResultWriter


# List of tournaments in chronological order. We aren't using the exact dates,
# they just need to be increasing.
ALL = [
    ("loco-2021", "2021-03-01"),
    ("pabst-2021", "2021-04-01"),
    ("charlottesville-2021", "2021-05-01"),
    ("seattle-2021", "2021-06-01"),
    ("hoodriver-2022", "2022-01-01"),
    ("sandiego-2022", "2022-02-01"),
    ("atx-2022", "2022-03-01"),
    ("boston-2022", "2022-04-01"),
    ("osc-2022", "2022-05-01"),
    ("3m-2022", "2022-05-21"),
    ("madison-2022", "2022-06-05"),
    ("stl-2022", "2022-06-21"),
    ("wgpo-earlybird-2022", "2022-07-08"),
    ("wordcup-d1-2022", "2022-07-09"),
    ("wordcup-d2-2022", "2022-07-10"),
    ("seattle-2022", "2022-07-24"),
    ("mn-2022", "2022-08-07"),
    ("potomac-2022", "2022-08-21"),
    ("loco-2022", "2022-09-05"),
    ("brattleboro-2022", "2022-10-02"),
    ("pabst-2022", "2022-10-07"),
    ("slingerlands-2022", "2022-11-12"),
    ("bend-2022", "2022-12-03"),
    ("la-2022", "2022-12-31"),
    ("nola-d1-2023", "2023-01-15"),
    ("nola-d2-2023", "2023-01-16"),
    ("hood-river-2023", "2023-02-20"),
    ("austin-2023", "2023-04-01"),
    ("silver-spring-2023", "2023-04-16"),
    ("slingerlands-2023", "2023-04-30"),
    ("austin-may-2023", "2023-05-06"),
    ("moco-2023", "2023-05-29"),
    ("austin-jun-2023", "2023-06-10"),
    ("stlouis-jun2023", "2023-06-11"),
    ("seattle-jul2023", "2023-07-16"),
    ("vancouver-aug2023", "2023-08-06"),
    ("austin-aug2023", "2023-08-11"),
    ("portland-aug2023", "2023-08-12"),
    ("columbia-2023", "2023-09-09"),
    ("austin-sep2023", "2023-09-16"),
    ("seattle-sept2023", "2023-09-30"),
    ("riorancho-oct2023", "2023-10-08"),
    ("potomac-oct2023", "2023-10-22"),
    ("texasstate-2023", "2023-10-29"),
    ("portland-nov2023", "2023-11-04"),
    ("nacc2023-d1", "2023-11-10"),
    ("nacc2023-d2", "2023-11-11"),
    ("nacc2023-d1p", "2023-11-12"),
    ("nacc2023-d2p", "2023-11-13"),
    ("nacc2023-afterword", "2023-11-14"),
    ("palmsprings-dec2023", "2023-12-10"),
    ("nola-open-2024", "2024-01-15"),
    ("nola-lite-2024", "2024-01-16"),
    ("portland-pub-jan2024", "2024-01-20"),
    ("hood-river-2024", "2024-02-19"),
    ("portland-pub-mar2024", "2024-03-02"),
    ("austin-atx2024", "2024-04-08"),
    ("portland-pub-apr132024", "2024-04-13"),
    ("portland-pub-apr142024", "2024-04-14"),
    ("championscup-2024", "2024-04-28"),
    ("portlandpub-may2024", "2024-05-04"),
    ("potomac-may2024", "2024-05-27"),
    ("seattle-may2024", "2024-05-28"),
    ("portlandpub-jun2024", "2024-06-15"),
    ("portlandpub-jul2024", "2024-07-20"),
    ("wordcup-2024-eb", "2024-07-24"),
    ("wordcup-2024-d1", "2024-07-30"),
    ("wordcup-2024-d2", "2024-07-31"),
    ("glenhaven-2024", "2024-08-04"),
    ("portlandpub-aug2024", "2024-08-25"),
    ("pdxwords-eb-2024", "2024-08-30"),
    ("lewes-2024", "2024-09-01"),
    ("pdxwords-2024", "2024-09-02"),
    ("portlandpub-oct2024", "2024-10-05"),
    ("seattle-oct262024", "2024-10-26"),
    ("seattle-oct272024", "2024-10-27"),
    ("columbia-2024", "2024-11-02"),
    ("portlandpub-nov2024", "2024-11-03"),
    ("portlandpub-dec2024", "2024-12-07"),
    ("sanfrancisco-dec2024", "2024-12-08"),
    ("vancouver-dec2024", "2024-12-15"),
    ("nola-lite-2025", "2025-01-19"),
    ("nola-open-2025", "2025-01-20"),
    ("hood-river-2025", "2025-02-17"),
    ("providence-apr2025", "2025-03-02"),
    ("providence-05apr2025", "2025-04-05"),
    ("portland-pub-12apr2025", "2025-04-12"),
    ("portland-pub-13apr2025", "2025-04-13"),
    ("championscup-2025", "2025-04-20"),
    ("rome-may2025", "2025-05-04"),
    ("bellingham-may2025", "2025-05-10"),
    ("seattle-may2025", "2025-05-24"),
    ("austin-atx2025", "2025-06-08"),
    ("denver-21jun2025", "2025-06-21"), 
    ("nova-jun2025", "2025-06-22"), 
    ("portlandpub-jun2025", "2025-06-29"),
    ("bend-jun2025", "2025-07-13"),
    ("wordcup-2025-eb", "2025-08-01"),
    ("wordcup-2025-d1", "2025-08-05"),
    ("wordcup-2025-d2", "2025-08-06"),
    ("pdxwords-eb-2025", "2025-08-29"),
    ("slingerlands-series1-2025", "2025-08-30"),
    ("slingerlands-series2-2025", "2025-08-31"),
    ("pdxwords-2025", "2025-09-01"),
    ("charlottesville-2025", "2025-10-04"),
]


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
    old_rating: float
    new_rating: float
    old_deviation: float
    new_deviation: float
    games: int

    @classmethod
    def from_tournament_player(cls, p):
        return cls(
            p.name,
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


class PlayerDB:
    """Player database."""

    def __init__(self):
        self.players = {}
        self.report = defaultdict(dict)

    def update(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                self.players[p.name] = Player.from_tournament_player(p)
                self.report[p.name][tournament.name] = (
                    PlayerReport.from_tournament_player(p)
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


def process_old_results(display_progress=True):
    d = os.path.join(os.path.dirname(__file__), "results")
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = PlayerDB()
    for prefix, date in ALL:
        if display_progress:
            print(f"Reading {prefix}")
        date = datetime.strptime(date, "%Y-%m-%d")
        res = hres[prefix]
        rat = hrat[prefix]
        t = playerdb.process_one_tournament(rat, res, prefix, date)
    return playerdb, t


def process_all_results(rating_file, result_file, name, tdate):
    playerdb, _ = process_old_results()
    # Now process the new tournament
    t = playerdb.process_one_tournament(rating_file, result_file, name, tdate)
    res_out = StringIO("")
    TabularResultWriter().write(res_out, t)
    show_file(res_out)
    print("-------------------------")
    return playerdb, t


def write_current_ratings(filename):
    playerdb, t = process_old_results()
    write_latest_ratings(filename, playerdb, t)


def write_report(filename, playerdb):
    fields = ("old_rating", "new_rating", "old_deviation", "new_deviation", "games")
    with open(filename, "w") as f:
        writer = csv.writer(f)
        header = [None, None] + [name for name, _ in ALL]
        writer.writerow(header)
        for p, rep in sorted(playerdb.report.items()):
            for x in fields:
                out = [p, x]
                for name, _ in ALL:
                    pl = rep.get(name)
                    entry = pl and getattr(pl, x)
                    out.append(entry)
                writer.writerow(out)


def write_latest_ratings(outfile, playerdb, t):
    # Display the most recent tournament
    print("-------------------------")
    print(f"Ratings adjustment for most recent tournament")
    res_out = StringIO("")
    TabularResultWriter().write(res_out, t)
    show_file(res_out)
    print("-------------------------")
    CSVResultWriter().write_file(outfile, t)
    # Also write out the complete rating list
    write_complete_ratings(playerdb)


def write_complete_ratings(playerdb, filename=None):
    if not filename:
        filename = "complete-ratings-list.csv"
    ps = playerdb.players.values()
    CSVRatingsFileWriter().write_file(filename, ps)
    print(f"Wrote all current ratings to {filename}")


def write_sim_report(filename):
    playerdb, t = process_old_results()
    write_report(filename, playerdb)
    return playerdb


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
        playerdb, t = process_all_results(rating_file, result_file, name, tdate)
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")
        # Also write out the complete rating list
        write_complete_ratings(playerdb)

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
        playerdb, t = process_all_results(rating_file, result_file, name, tdate)
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")
        print(f"Wrote tournament ratings to {outfile}")
        # Also write out the complete rating list
        write_complete_ratings(playerdb)

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
