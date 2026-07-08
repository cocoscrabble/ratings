#!/usr/bin/python

import argparse
from datetime import datetime, timedelta
import logging
import math
import sys
import textwrap
import tkinter as tk
from tkinter import filedialog, ttk

from coco_ratings.io import (
    CSVRatingsFileReader,
    CSVResultWriter,
    ResultCSVReader,
    RTFileReader,
    RTFileWriter,
    TabularResultWriter,
    TouReader,
)
from coco_ratings.types import Player


# Set up log file
logging.basicConfig(filename="coco_ratings.log", encoding="utf-8", level=logging.DEBUG)


# -----------------------------------------------------
# Ratings calculations


class RatingsCalculator:
    """Class to organise ratings calculation code in one place."""

    def __init__(self, beta: float = 5):
        # tau is a tuning parameter to get as accurate results as
        # possible, and should be set up front. The value here is from
        # Taral Seierstad's rating system for Norwegian scrabble.
        self.tau = 90

        # beta is rating points per point of expected spread
        # eg, beta = 5, 100 ratings difference = 20 difference in
        # expected spread.
        # (Should we try varying beta based on ratings difference?)
        self.beta = beta

    def calc_initial_ratings(self, section):
        """Rate all unrated players in a section."""

        # Set pre-tournament rating to 1500 and deviation to 400 to start
        # Rerun the "calculate ratings for unrated players" part repeatedly,
        #   using the previously calculated rating as their initial rating
        #   until the output rating for these players equals the input rating

        # criteria for ratings convergence
        MAX_ITERATIONS = 50
        EPS = 0.0001

        # Manual seed
        MANUAL_SEED = 1500

        rated_opponent_sum = sum(p.init_rating for p in section.get_rated_players())
        rated_opponent_avg = rated_opponent_sum / len(section.get_players())
        if rated_opponent_avg < 300:
            logging.debug(
                "Rated player avg = %f; setting to manual seed", rated_opponent_avg
            )
            rated_opponent_avg = MANUAL_SEED

        converged = False
        iterations = 0
        while not converged and iterations < MAX_ITERATIONS:
            # converged is set to false in the loop below if any player's
            # rating changes in this iteration.
            converged = True

            for p in section.get_unrated_players():
                unrated_opps = [o for o in p.get_opponents() if o.is_unrated]
                if unrated_opps:
                    unrated_opps_pct = len(unrated_opps) / len(p.get_opponents())
                    if unrated_opps_pct >= 0.4:
                        p.set_init_rating(rated_opponent_avg)
                pre_rating = p.init_rating
                self.calc_new_rating_for_player(p)  # calculates rating as usual
                converged = converged and (abs(pre_rating - p.new_rating) < EPS)
                p.set_init_rating(p.new_rating)
                logging.debug(f"Rating unrated player {p}: {p.new_rating}")

            iterations = iterations + 1

    def _player_multiplier(self, player):
        # Calculate a multiplier based on initial ratings, then adjust it
        # based on career games.
        if player.init_rating > 2000:
            multiplier = 0.5
        elif player.init_rating > 1800:
            multiplier = 0.75
        else:
            multiplier = 1.0

        if player.career_games < 200:
            multiplier = 1.0
        elif player.career_games > 1000:
            multiplier = 0.5
        elif player.career_games > 100:
            multiplier = min(multiplier, 1.0 - (player.career_games / 1800))

        return multiplier

    def calc_new_rating_for_player(self, player):
        """An implementation of the Norwegian rating system.

        Rates a single player based on spread.
        """

        tau = self.tau
        beta = self.beta

        mu = player.init_rating
        logging.debug(
            "rating %s: initial = %d, multiplier = %f",
            player.name,
            mu,
            self._player_multiplier(player),
        )

        # Deviation is adjusted for inactive time when player is loaded
        sigma = player.init_rating_deviation

        rhos = []  # opponent uncertainty factor
        nus = []  # performance rating by game
        games = []  # games considered for rating
        for g in player.games:
            opponent = g.opponent
            if opponent == player or g.opp_score == 0 or g.score == 0:
                logging.debug("  skipping bye / forfeit")
                continue  # skip byes
            opponent_mu = opponent.init_rating
            opponent_sigma = opponent.init_rating_deviation
            g_rho = (beta**2) * (tau**2) + opponent_sigma**2
            g_nu = opponent_mu + (beta * g.spread)
            logging.debug(
                "  opp %s (μ=%.2f σ=%.2f) -> (ρ=%.2f ν=%.2f)",
                opponent.name,
                opponent_mu,
                opponent_sigma,
                g_rho,
                g_nu,
            )
            rhos.append(g_rho)
            nus.append(g_nu)
            games.append(g)
        # sum of inverse of uncertainty factors (to find 'effective'
        # deviation)
        sum1 = sum(1 / rho for rho in rhos)
        # sum of (INDIVIDUAL perfrat divided by opponent's sigma)
        sum2 = sum(nu / rho for nu, rho in zip(nus, rhos))
        # take invsquare of original dev, add inv of new sum of devs,
        # flip it back to get 'effective sigmaPrime'
        invsigma_prime = (1.0 / (sigma**2)) + sum1
        sigma_prime = 1.0 / invsigma_prime
        # calculate new rating using NEW sigmaPrime
        mu_prime = sigma_prime * ((mu / (sigma**2)) + sum2)
        delta = mu_prime - mu
        multiplier = self._player_multiplier(player)
        mu_prime = mu + (delta * multiplier)

        # Debug per-game rating change
        logging.debug("Per game rating changes for %s", player.name)
        base = sigma_prime * (mu / (sigma**2))
        n_games = len(games)
        base_delta = (player.init_rating - base) / n_games if n_games else 0
        logging.debug(
            "  base from opp ratings: %.2f (%d games, baseline Δ = %.2f)",
            base,
            n_games,
            base_delta,
        )
        sum_d = 0
        for game, g_rho, g_nu in zip(games, rhos, nus):
            g_mu = sigma_prime * (g_nu / g_rho)
            base += g_mu
            d = g_mu - base_delta
            sum_d += d
            logging.debug(
                "  %20s (%4d): \t Δ %6.2f \t Σ %6.2f \t d %6.2f \t Σd %6.2f \t ",
                game.opponent.name,
                game.spread,
                g_mu,
                base,
                d,
                sum_d,
            )

        # muPrime = mu + change
        # Don't set rating lower than 300
        logging.info("Rated %s: %f -> %f", player.name, player.init_rating, mu_prime)
        player.new_rating = max(round(mu_prime), 300)

        # if (player.new_rating < 1000): #believes all lousy players can improve :))
        #  sigmaPrime += math.sqrt(1000 - player.new_rating)
        try:
            player.new_rating_deviation = round(math.sqrt(sigma_prime), 2)
            logging.info(
                "New deviation for %s: %f -> %f",
                player.name,
                player.init_rating_deviation,
                player.new_rating_deviation,
            )
        except ValueError:
            print("ERROR: sigmaPrime {0}".format(sigma_prime))


# -----------------------------------------------------
# Internal data structures


class Tournament:
    """All data for a tournament."""

    def __init__(self, ratings_file, result_file, name=None, date=None):
        self.player_list = PlayerList(ratings_file)
        self.parse_results_file(result_file, name, date)

    def parse_results_file(self, file, name, date):
        if file.endswith(".csv") or file.endswith(".tsv"):
            # .csv file needs name and date as args for now
            reader = ResultCSVReader(self.player_list, name, date)
            reader.parse(file)
            self.sections = reader.sections
            self.name = name
            self.date = date
        elif file.endswith(".tou"):
            # .tou file contains the name and date
            reader = TouReader(self.player_list)
            reader.parse(file)
            self.sections = reader.sections
            self.name = reader.tournament_name
            self.date = reader.tournament_date
        else:
            raise ValueError(f"No reader for {file}")

    def calc_ratings(self, beta: float = 5):
        logging.debug("--------------Calculating ratings for %s", self.name)
        rc = RatingsCalculator(beta)
        for s in self.sections:
            # FIRST: Calculate initial ratings for all unrated players
            rc.calc_initial_ratings(s)
            # THEN: Calculate new ratings for rated players
            for p in s.get_rated_players():
                rc.calc_new_rating_for_player(p)

    def output_ratfile(self, out_file):
        byes = {
            "Yy bye",
            "A Bye",
            "B Bye",
            "ZZ Bye",
            "Zz Bye",
            "Zy bye",
            "Bye One",
            "Bye Two",
            "Bye Three",
            "Bye Four",
            "Y Bye",
            "Z Bye",
            "Bye",
        }
        players = [
            p for p in self.player_list.get_ranked_players() if p.name not in byes
        ]
        RTFileWriter().write_file(out_file, players)

    def output_active_ratfile(self, out_file):
        with open("removed_people.txt", "r") as d:
            deceased = [x.rstrip() for x in d.readlines()]
        players = []
        for p in self.player_list.get_ranked_players():
            threshold = self.date - timedelta(days=731)
            active = p.last_played > threshold
            if active and p.name not in deceased:
                players.append(p)

        RTFileWriter().write_file(out_file, players)


class PlayerList:
    """A global ratings list."""

    def __init__(self, ratfile=None):
        self.parse_ratfile(ratfile)

    def parse_ratfile(self, ratfile):
        if ratfile:
            # Load all current players from ratfile
            if ratfile.endswith(".csv") or ratfile.endswith(".tsv"):
                self.players = CSVRatingsFileReader().parse(ratfile)
            else:
                self.players = RTFileReader().parse(ratfile)
        else:
            self.players = {}

    def add_new_player(self, name):
        self.players[name] = Player.new_unrated(name)

    def get_ranked_players(self):
        return sorted(
            self.players.values(),
            key=lambda p: p.new_rating,
            reverse=True,
        )

    def find_or_add_player(self, name):
        if name not in self.players:
            self.add_new_player(name)
        return self.players[name]


# -----------------------------------------------------
# CLI


def make_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, default="", help="Tournament name")
    parser.add_argument(
        "--date", type=str, default="", help="Tournament date (yyyy-mm-dd)"
    )
    parser.add_argument("--rating-file", type=str, help="Ratings file")
    parser.add_argument("--result-file", type=str, help="Results file")
    return parser


def run_cli():
    parser = make_arg_parser()
    args = parser.parse_args()
    date = datetime.strptime(args.date, "%Y-%m-%d")
    t = Tournament(args.rating_file, args.result_file, args.name, date)
    t.calc_ratings()
    print("Writing results to output.txt and output.csv")
    TabularResultWriter().write_file("output.txt", t)
    CSVResultWriter().write_file("output.csv", t)
    t.output_ratfile("output.RT")


# -----------------------------------------------------
# GUI


class File:
    def __init__(self, parent, name, status, save_as=False):
        self.name = name
        self.status = status
        self.save_as = save_as
        self.label = ttk.Label(parent, text=f"{name}:")
        self.file = None
        self.file_label = ttk.Label(parent, text="")
        b = "Save as" if self.save_as else "Open"
        self.button = ttk.Button(parent, text=b)
        self.button["command"] = self.select_file
        self.set_file_label()

    def set_file_label(self):
        if self.file:
            text = self.file
            style = "BW.TLabel"
        else:
            text = "[No file selected]"
            style = "GW.TLabel"
        self.file_label.configure(text=text, style=style)

    def select_file(self):
        filetypes = (("csv files", "*.?sv"), ("All files", "*.*"))
        if self.save_as:
            filename = filedialog.asksaveasfilename(
                title="Save new ratings", filetypes=filetypes
            )
        else:
            filename = filedialog.askopenfilename(
                title=f"Open {self.name} file", filetypes=filetypes
            )
        self.file = filename
        self.set_file_label()
        self.status.set_status(f"Set {self.name} file")


class FilesWidget(ttk.Frame):
    def __init__(self, container, status):
        super().__init__(container)
        self.files = {}
        self.status = status
        self._init_widgets()

    def get_files(self):
        return [self.files[x].file for x in ("Ratings", "Results", "New results")]

    def _add_file(self, name, row, save_as=False):
        f = File(self, name, self.status, save_as)
        self.files[name] = f
        f.label.grid(column=0, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.file_label.grid(column=1, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.button.grid(column=2, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)

    def _init_widgets(self):
        self._add_file("Ratings", 0)
        self._add_file("Results", 1)
        self._add_file("New results", 2, save_as=True)
        self.grid(padx=10, pady=0, sticky=tk.NSEW)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("COCO Ratings Calculator")
        self.geometry("1200x800")
        self.init_style()
        self.frame = ttk.Frame(self)
        self._init_widgets()

    def _init_widgets(self):
        label = self._instructions()
        self.output = ttk.Label(self.frame)
        self.files = FilesWidget(self.frame, status=self)
        buttonbox = ttk.Frame(self.frame)
        button1 = ttk.Button(buttonbox, text="Calculate new ratings")
        button1["command"] = self.calculate_ratings
        button2 = ttk.Button(buttonbox, text="Recalculate latest tournament")
        button2["command"] = self.recalculate_ratings
        # layout widgets
        label.grid(row=0)
        self.files.grid(row=1, pady=10, sticky=tk.EW)
        self.files.grid_columnconfigure(1, weight=1)
        button1.grid(row=0, column=0, padx=10, pady=10)
        button2.grid(row=0, column=1, padx=10, pady=10)
        buttonbox.grid(row=2, pady=20)
        self.output.grid(row=3, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Export a ratings file and a results file from a spreadsheet in CSV format
        * Load both files into the fields below.
        * Select a file to save the new ratings to.
        * Click "Calculate Ratings"

        Expected csv columns:
          rating: Name, Rating
          results: Submitted On, Round, Winner, Score, Opponent, Score

        Keep the csv header row, the script skips the first row.
        """)
        ret = tk.Text(self.frame, width=80, height=14)
        ret.insert("end", text)
        ret.config(state="disabled")
        return ret

    def init_style(self):
        style = ttk.Style()
        style.configure("BW.TLabel", foreground="black", background="white")
        style.configure("GW.TLabel", foreground="grey", background="white")
        return style

    def set_status(self, text):
        self.output.configure(text=text)

    def calculate_ratings(self):
        rating_file, result_file, outfile = self.files.get_files()
        if not (rating_file and result_file and outfile):
            self.set_status("Some filenames are not set")
            return
        name = "Tournament name"
        tdate = datetime.today()
        t = Tournament(rating_file, result_file, name, tdate)
        t.calc_ratings()
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")

    def recalculate_ratings(self):
        # implemented in all_ratings.py
        pass


class SimulationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("COCO Ratings Simulator")
        self.geometry("1200x800")
        self.init_style()
        self.frame = ttk.Frame(self)
        self._init_widgets()

    def _init_widgets(self):
        label = self._instructions()
        self.output = ttk.Label(self.frame)
        self.beta_input = tk.StringVar()
        inputbox = ttk.Frame(self.frame)
        beta_label = ttk.Label(inputbox, text="beta = ")
        self.entry = ttk.Entry(inputbox, textvariable=self.beta_input)
        buttonbox = ttk.Frame(self.frame)
        button1 = ttk.Button(buttonbox, text="Run simulation")
        button1["command"] = self.run_simulation
        button2 = ttk.Button(buttonbox, text="Quit")
        button2["command"] = self.quit
        # layout widgets
        label.grid(row=0)
        beta_label.grid(row=0, column=0)
        self.entry.grid(row=0, column=1, columnspan=2)
        inputbox.grid(row=1, pady=10, sticky=tk.EW)
        button1.grid(row=0, column=0, padx=10, pady=10)
        button2.grid(row=0, column=1, padx=10, pady=10)
        buttonbox.grid(row=2, pady=20)
        self.output.grid(row=3, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Pick a value for beta (default = 5)
        * Click on "Run Simulation"

        beta is rating points difference per point of expected spread
        If, for instance, beta = 5, it means that if a player is rated 100
        points above another player, the spread in games played between the two
        players should on average be 100 / 5 = 20 points in favour of the first
        player. i.e. the lower beta is, the more the higher-rated player is
        expected to win by.

        The result will be written to a csv file which can be imported into
        a spreadsheet.
        """)
        ret = tk.Text(self.frame, width=80, height=14)
        ret.insert("end", text)
        ret.config(state="disabled")
        return ret

    def init_style(self):
        style = ttk.Style()
        style.configure("BW.TLabel", foreground="black", background="white")
        style.configure("GW.TLabel", foreground="grey", background="white")
        return style

    def set_status(self, text):
        self.output.configure(text=text)

    def quit(self):
        sys.exit(0)

    def run_simulation(self):
        # implemented in all_ratings.py
        pass


def run_gui():
    w = App()
    w.mainloop()


if __name__ == "__main__":
    # DO NOT run the standalone rating script, always run all_rating
    print()
    print("Run `python all_rating.py` to rate a new tournament.")
    print()
    sys.exit(0)

    # Comment out the above lines to run the standalone script.
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
