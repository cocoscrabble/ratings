"""Database of tournaments.

Currently maintained in a CSV file, in the order they are to be rated.

Columns: `FancyName, Division, City, Name, Tournament, Filename, Date, Order`.
`Date` is `yyyy-mm-dd`. (It used to be carried redundantly as separate Month,
Day and Year columns as well; those are gone.) `Order` is optional and only matters when two
tournaments share a date: the replay carries ratings forward, so a player who
appears in both is rated in whichever order these are listed, and the result
differs. Give each same-day event an `Order` (1, 2, 3 …) to say which came
first. Rows that leave it blank sort before any numbered row on that date and
then by filename, which is what every row did before the column existed.
"""

import csv
from dataclasses import dataclass

from coco_ratings.paths import TOURNAMENTS_CSV


# Exported as csv from google doc
DBFILE = TOURNAMENTS_CSV


@dataclass
class TournamentEntry:
    fancy_name: str
    division: str
    city: str
    name: str
    tournament: str
    filename: str
    # yyyy-mm-dd; normalised in post-init so string compares are date compares
    date: str = ""
    # Tie-break for tournaments sharing a date: lower is rated first. Optional,
    # so a row that predates the column still parses. See sort_order below.
    order: str = ""

    def __post_init__(self):
        self.date = self.normalise_date(self.date)

        # Blank (or unparseable) sorts first, which keeps the pre-column
        # behaviour for every row that does not need disambiguating.
        try:
            self.sort_order = int(str(self.order).strip())
        except ValueError:
            self.sort_order = 0

    @staticmethod
    def normalise_date(value):
        """Zero-pad a yyyy-mm-dd date so it sorts and compares as a string.

        The replay orders tournaments by comparing these strings (and the golden
        test slices the history with one), so `2024-5-1` has to become
        `2024-05-01`. A date that cannot be read at all is left as-is rather
        than guessed at: it will sort oddly and be noticed, which beats a
        plausible wrong date silently reordering the history.
        """
        parts = str(value).strip().split("-")
        if len(parts) != 3:
            return str(value).strip()
        try:
            year, month, day = (int(p) for p in parts)
        except ValueError:
            return str(value).strip()
        return f"{year:04d}-{month:02d}-{day:02d}"


class TournamentDB:
    """Overall list of tournaments in chronological order.

    Ratings are a running total, so the order tournaments are replayed in is
    part of the result: two events on the same day that share players give
    different ratings depending on which is rated first. The date alone cannot
    express that, hence the optional `Order` column — see the module docstring.
    """

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
        entries = [TournamentEntry(*row) for row in data]
        # Filename remains the last resort so that rows with no Order keep the
        # ordering they have always had.
        self.tournaments = sorted(
            entries, key=lambda x: (x.date, x.sort_order, x.filename)
        )


if __name__ == "__main__":
    tdb = TournamentDB.read_csv()
    for t in tdb.tournaments:
        print(f"{t.filename} {t.date}")
