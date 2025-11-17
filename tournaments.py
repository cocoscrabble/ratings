"""Database of tournaments.

Currently maintained in a CSV file.
"""

import csv
from dataclasses import dataclass


# Exported as csv from google doc
DBFILE = "data/tournaments.csv"


@dataclass
class Tournament:
    fancy_name: str
    division: str
    city: str
    month: str
    day: str
    year: str
    name: str
    tournament: str
    filename: str
    # handled in post-init, format = yyyy-mm-dd
    date: str = ""

    def __post_init__(self):
        def convert(s):
            try:
                i = int(s.strip())
            except ValueError:
                # We need to default to 1 if there is no entry for day, since
                # it needs to be parsed as a date and 0 is invalid
                i = 1
            return i

        year = convert(self.year)
        month = convert(self.month)
        day = convert(self.day)
        self.date = f"{year}-{month:02d}-{day:02d}"


class TournamentDB:
    """Overall list of tournaments in chronological order."""

    @classmethod
    def read_csv(cls, file=DBFILE):
        rows = []
        with open(file, "r") as f:
            reader = csv.reader(f)
            # skip headings
            next(reader)
            for row in reader:
                rows.append(row)
        return cls(rows)

    def __init__(self, data: list[list[str]]):
        entries = [Tournament(*row) for row in data]
        self.tournaments = sorted(entries, key=lambda x: (x.date, x.filename))


if __name__ == "__main__":
    tdb = TournamentDB.read_csv()
    for t in tdb.tournaments:
        print(f"{t.filename} {t.date}")
