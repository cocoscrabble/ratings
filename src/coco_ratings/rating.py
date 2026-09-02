#!/usr/bin/python

import argparse
from datetime import datetime, timedelta
import logging
import sys

from coco_ratings.core import Player, RatingsCalculator  # noqa: F401

from coco_ratings.io import (
    CSVRatingsFileReader,
    CSVResultWriter,
    ResultCSVReader,
    RTFileReader,
    RTFileWriter,
    TabularResultWriter,
    TouReader,
)

# Module logger, not the root one: this is a library, and an application
# importing it must be able to quiet the engine without silencing itself.
logger = logging.getLogger(__name__)

# RatingsCalculator is re-exported above: it lives in coco_ratings.core now (so
# it can be imported without the io layer), but tests and callers have always
# reached it through this module.

# -----------------------------------------------------
# Internal data structures


class Tournament:
    """All data for a tournament."""

    def __init__(self, ratings_file, result_file, name=None, date=None):
        self.player_list = PlayerList(ratings_file)
        # Which identity the results file keyed players by; see
        # ResultsReader.keyed_by. Carried up so callers can report which
        # corpus is which, and so retiring the name-keyed path has a way to
        # measure its own progress.
        self.keyed_by = "name"
        self.parse_results_file(result_file, name, date)

    def parse_results_file(self, file, name, date):
        if file.endswith(".csv") or file.endswith(".tsv"):
            # .csv file needs name and date as args for now
            reader = ResultCSVReader(self.player_list, name, date)
            reader.parse(file)
            self.sections = reader.sections
            self.keyed_by = reader.keyed_by
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
        logger.debug("--------------Calculating ratings for %s", self.name)
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

    def add_new_player(self, name, number=None):
        player = Player.new_unrated(name, number)
        self.players[player.key] = player
        return player

    def get_ranked_players(self):
        return sorted(
            self.players.values(),
            key=lambda p: p.new_rating,
            reverse=True,
        )

    def find_or_add_player(self, name, number=None):
        """The player this (name, number) refers to, creating them if new.

        Players are filed under their number when the file gave one and under
        their name when it did not, so a number-bearing file keeps two
        same-named players apart.

        The two halves of a tournament need not agree about which form they
        are in: the ratings file is a Google Sheets export with no numbers to
        give, while the results file may come from Baxter and have them. So a
        player met with a number who is already on file under their name is
        the *same person*, newly identified -- adopt the number and re-file
        them, rather than seeding a duplicate at 1500 and throwing away the
        rating they came in with.
        """
        player = Player.new_unrated(name, number)
        if player.key in self.players:
            return self.players[player.key]
        if player.number and name in self.players:
            existing = self.players.pop(name)
            existing.number = player.number
            self.players[player.key] = existing
            return existing
        self.players[player.key] = player
        return player


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


if __name__ == "__main__":
    # DO NOT run this module directly; use `coco-rate` (see pipeline.py),
    # which rates a tournament in the context of all prior ones. The GUI now
    # lives in coco_ratings.gui.
    print()
    print("Run `coco-rate` to rate a new tournament.")
    print()
    sys.exit(0)

    # Comment out the above lines to run the single-tournament CLI directly.
    run_cli()
