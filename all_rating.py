"""Rate a sequence of tournaments.

Carries forward ratings and std deviation for repeat players. This is a stopgap
measure until we put an actual database in place.
"""

from dataclasses import dataclass
from datetime import datetime
import glob
import os
from io import StringIO

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
]


@dataclass
class Player:
    name: str
    rating: float
    deviation: float
    games: int

    @classmethod
    def from_tournament_player(cls, p):
        return cls(p.name, p.new_rating, p.new_rating_deviation, p.career_games)


class PlayerDB:
    """Player database."""

    def __init__(self):
        self.players = {}

    def update(self, tournament):
        for s in tournament.sections:
            for p in s.get_players():
                self.players[p.name] = Player.from_tournament_player(p)


def adjust_tournament(playerdb, tournament):
    for s in tournament.sections:
        for p in s.get_players():
            if p.name not in playerdb.players:
                continue
            dbp = playerdb.players[p.name]
            if p.init_rating != dbp.rating:
                print(f"Adjusting: {p.name} : {p.init_rating} -> {dbp.rating}")
            p.init_rating = dbp.rating
            p.init_rating_deviation = dbp.deviation
            p.career_games = dbp.games



def show_file(f):
    f.seek(0)
    for line in f.readlines():
        print(line.strip())


def main():
    d = os.path.join(os.path.dirname(__file__), "results")
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = PlayerDB()
    for prefix, date in ALL:
        print(f"Reading {prefix}")
        date = datetime.strptime(date, '%Y-%m-%d')
        res = hres[prefix]
        rat = hrat[prefix]
        t = Tournament(rat, res, prefix, date)
        adjust_tournament(playerdb, t)
        t.calc_ratings()
        playerdb.update(t)
        res_out = StringIO('')
        TabularResultWriter().write(res_out, t)
        show_file(res_out)
        print("-------------------------")
        
        
        


    


if __name__ == '__main__':
    main()

