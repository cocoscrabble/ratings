"""Rate a sequence of tournaments.

Carries forward ratings and std deviation for repeat players. This is a stopgap
measure until we put an actual database in place.
"""

from datetime import datetime
import glob
import os
from io import StringIO

from coco_ratings.io import TabularResultWriter
from coco_ratings.milestone import Milestone, MilestoneError
from coco_ratings.paths import MILESTONE_DIR, RESULTS_DIR
from coco_ratings.players import PlayerDB
from coco_ratings.ratingsdb import RatingsDB
from coco_ratings.reports import (
    show_file,
    write_latest_ratings,
    write_report,
)
from coco_ratings.tournaments import TournamentDB


# Passed as ``milestone`` to mean "the committed one, if there is one".
COMMITTED = object()


def process_old_results(
    display_progress=False,
    beta: float = 5,
    until: str | None = None,
    quiet: bool = False,
    milestone=COMMITTED,
    stop_after: str | None = None,
):
    """Replay the tournament history in order and return (ratingsdb, latest).

    By default the replay starts from the committed rating milestone
    (``milestone/``): tournaments it froze keep their published ratings and are
    only read for their records, and the current code rates everything after
    it. Pass ``milestone=None`` for a full replay from the first tournament,
    which is what the engine's own tests and research (the golden test, beta
    simulations, rating archaeology) want: they are about the code, not about
    the published numbers. See ``coco_ratings.milestone``.

    `until` is an optional inclusive yyyy-mm-dd cutoff: tournaments dated after
    it are skipped. Ratings are a running total over the whole history, so this
    is only meaningful for pinning a reproducible prefix of it (see
    tests/test_golden.py) — never for producing the current ratings.

    `stop_after` stops after rating the named tournament; it is how a milestone
    is cut part-way through the history.

    `quiet` silences the `!!` warnings about missing files. They are worth seeing
    on a real run, but a test that replays the history several times just buries
    the test runner's output in them.
    """

    def warn(msg: str) -> None:
        if not quiet:
            print(msg)

    if milestone is COMMITTED:
        milestone = Milestone.load(MILESTONE_DIR)
        if milestone is None and os.environ.get("COCO_MILESTONE_DIR"):
            # A deployment that names its milestone and cannot find it must not
            # fall back to a full replay: that is a silent rewrite of every
            # published rating.
            raise MilestoneError(f"no milestone at {MILESTONE_DIR}")

    d = str(RESULTS_DIR)
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    playerdb = PlayerDB.read_csv()
    tournamentdb = TournamentDB.read_csv()
    ratingsdb = RatingsDB(playerdb, beta)
    ratingsdb.rated = []  # filenames in the order processed, frozen ones first
    latest = None

    entries = tournamentdb.tournaments
    if milestone is not None:
        frozen, entries = milestone.plan(entries, hres)
        for entry in frozen:
            prefix = entry.filename
            date = datetime.strptime(entry.date, "%Y-%m-%d")
            latest = ratingsdb.process_frozen_tournament(
                hrat.get(prefix), hres[prefix], prefix, date, milestone
            )
            ratingsdb.rated.append(prefix)
            if prefix == stop_after:
                raise MilestoneError(f"{prefix} is already frozen")
        milestone.restore_state(ratingsdb)

    for entry in entries:
        prefix, date = entry.filename, entry.date
        if until is not None and date > until:
            # Dates are zero-padded yyyy-mm-dd, so a string compare is a date
            # compare. Entries are already sorted, but skip rather than break so
            # the loop stays independent of the ordering.
            continue
        if not prefix:
            warn(f"!! No results file for {entry.fancy_name}")
            continue
        if display_progress:
            print(f"Reading {prefix}")
        date = datetime.strptime(date, "%Y-%m-%d")
        res = hres.get(prefix)
        if res is None:
            # Can't rate a tournament with no results; skip it loudly.
            warn(f"!! No results file for {prefix}, skipping")
            continue
        # The ratings file is optional: returning players are rated from the
        # accumulated carry-forward ratings, and first-timers are seeded from
        # their results. A missing file only affects genuine first-timers.
        rat = hrat.get(prefix)
        if rat is None:
            warn(f"!! No ratings file for {prefix}, rating from accumulated ratings")
        latest = ratingsdb.process_one_tournament(rat, res, prefix, date)
        ratingsdb.rated.append(prefix)
        if prefix == stop_after:
            break
    if latest is None:
        raise RuntimeError("No tournaments with result files were processed")
    if stop_after is not None and ratingsdb.rated[-1] != stop_after:
        raise ValueError(f"{stop_after} was never rated")
    if ratingsdb.missing_ids:
        names = ", ".join(sorted(ratingsdb.missing_ids))
        warn(
            f"!! {len(ratingsdb.missing_ids)} rated name(s) with no row in "
            f"data/players.csv: {names}"
        )
    return ratingsdb, latest


def results_files():
    """filename -> results file, for every results file in results/."""
    return {
        os.path.basename(f)[:-12]: f
        for f in glob.glob(f"{RESULTS_DIR}/*results.?sv")
    }


def cut_milestone(through: str | None = None, directory=MILESTONE_DIR):
    """Freeze everything up to and including ``through`` (default: all).

    Rates with the current code from the committed milestone, then writes the
    new milestone over it. The cut can only add frozen history; see
    ``milestone.cut``.
    """
    from coco_ratings import milestone as ms

    previous = Milestone.load(directory)
    ratingsdb, _ = process_old_results(
        quiet=True, milestone=previous, stop_after=through
    )
    return ms.cut(
        directory, ratingsdb, ratingsdb.rated, results_files(),
        previous=previous, beta=ratingsdb.beta,
    )


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


def write_sim_report(filename, beta: float = 5):
    # A simulation asks what the whole history would look like under another
    # beta, so it must not start from ratings frozen under this one.
    ratingsdb, _ = process_old_results(beta=beta, milestone=None)
    write_report(filename, ratingsdb)
    return ratingsdb


def run_simulation(beta: float = 5):
    filename = f"run-with-beta-{beta}-report.csv"
    pdb = write_sim_report(filename, beta)
    print(f"Wrote simulation report to {filename}")
    return pdb
