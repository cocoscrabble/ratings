"""Player statistics."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from all_rating import process_old_results


@dataclass
class Player:
    name: str
    tournaments: int
    games: int
    last_played: datetime


class Statistics:
    """Statistics on playerdb."""

    def __init__(self, playerdb):
        self.db = playerdb
        self.stats = {}

    def calc_stats(self):
        for name, report in sorted(self.db.report.items()):
            tournaments = len(report.values())
            p = self.db.players[name]
            self.stats[p.name] = Player(name, tournaments, p.games, p.last_played)

    def display_stats(self, filename):
        with open(filename, "w") as f:
            f.write("Name, Tournaments, Games, Last Played\n")
            for _, p in sorted(self.stats.items()):
                dt = p.last_played.strftime("%Y-%m-%d")
                f.write(f"{p.name}, {p.tournaments}, {p.games}, {dt}\n")


if __name__ == "__main__":
    filename = "player-stats.csv"
    print("Calculating stats...")
    db, _ = process_old_results(display_progress=False)
    s = Statistics(db)
    s.calc_stats()
    s.display_stats(filename)
    print(f"Wrote stats to {filename}")
