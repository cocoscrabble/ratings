"""File output for the ratings pipeline.

Pure writers: given an already-computed ``RatingsDB`` (and optionally the most
recent tournament), render the tabular / CSV rating reports. These know nothing
about the history replay itself, so ``pipeline`` imports them, not vice versa.
"""

import csv
from io import StringIO

from coco_ratings.io import CSVResultWriter, TabularResultWriter
from coco_ratings.ratingsdb import CSVRatingsFileWriter
from coco_ratings.tournaments import TournamentDB


def show_file(f):
    f.seek(0)
    for line in f.readlines():
        print(line.strip())


def write_report(filename, ratingsdb):
    fields = ("old_rating", "new_rating", "old_deviation", "new_deviation", "games")
    # One column per tournament, in chronological order. TournamentDB filenames
    # are the same keys the report is indexed by (see RatingsDB.update).
    tournaments = [t.filename for t in TournamentDB.read_csv().tournaments if t.filename]
    with open(filename, "w") as f:
        writer = csv.writer(f)
        header = [None, None] + tournaments
        writer.writerow(header)
        for p, rep in sorted(ratingsdb.report.items()):
            for x in fields:
                out = [p, x]
                for name in tournaments:
                    pl = rep.get(name)
                    entry = pl and getattr(pl, x)
                    out.append(entry)
                writer.writerow(out)


def write_latest_ratings(outfile, ratingsdb, t):
    # Display the most recent tournament
    print("-------------------------")
    print("Ratings adjustment for most recent tournament")
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
