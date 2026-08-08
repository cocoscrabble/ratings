"""Two tournaments on the same day need an explicit order.

Ratings are carried forward, so when a player appears in both halves of a
same-day double-header the result depends on which is rated first. The date
cannot express that, so tournaments.csv has an optional `Order` column.
"""

import unittest

from coco_ratings.tournaments import TournamentDB, TournamentEntry


def row(filename, date, order=None):
    """A tournaments.csv row: FancyName,Division,City,Name,Tournament,Filename,Date[,Order]."""
    cells = ["Fancy", "", "City", "", "", filename, date]
    if order is not None:
        cells.append(order)
    return cells


def order_of(*rows):
    return [t.filename for t in TournamentDB(list(rows)).tournaments]


class TournamentOrderTest(unittest.TestCase):
    def test_date_still_dominates(self):
        # Order only ever breaks ties; it cannot reorder different days.
        self.assertEqual(
            order_of(row("b", "2024-05-02", "1"), row("a", "2024-05-01", "9")),
            ["a", "b"],
        )

    def test_same_day_uses_order_not_filename(self):
        # Alphabetically 'zeta' follows 'alpha'; the Order column overrides it.
        self.assertEqual(
            order_of(row("alpha", "2024-05-01", "2"), row("zeta", "2024-05-01", "1")),
            ["zeta", "alpha"],
        )

    def test_the_nacc_case(self):
        # The live example: playoffs are rated after both divisions, where
        # sorting by filename alone would put d1p between d1 and d2.
        self.assertEqual(
            order_of(
                row("nacc-d1", "2023-11-10", "1"),
                row("nacc-d1p", "2023-11-10", "3"),
                row("nacc-d2", "2023-11-10", "2"),
                row("nacc-d2p", "2023-11-10", "4"),
            ),
            ["nacc-d1", "nacc-d2", "nacc-d1p", "nacc-d2p"],
        )

    def test_blank_order_keeps_filename_ordering(self):
        # Every row predating the column has a blank Order, and must sort
        # exactly as it did before: by date, then filename.
        self.assertEqual(
            order_of(row("b", "2024-05-01", ""), row("a", "2024-05-01", "")),
            ["a", "b"],
        )

    def test_row_without_the_column_at_all_still_parses(self):
        # tournaments.csv may be re-exported from a sheet that lacks the column.
        self.assertEqual(
            order_of(row("b", "2024-05-01"), row("a", "2024-05-01")), ["a", "b"]
        )

    def test_blank_sorts_before_numbered_on_the_same_day(self):
        self.assertEqual(
            order_of(row("a", "2024-05-01", "1"), row("b", "2024-05-01", "")),
            ["b", "a"],
        )

    def test_unparseable_order_is_ignored_not_fatal(self):
        # One bad cell must not take down the whole replay.
        entry = TournamentEntry(*row("a", "2024-05-01", "first"))
        self.assertEqual(entry.sort_order, 0)

    def test_order_is_numeric_not_lexicographic(self):
        # "10" must sort after "9", which string comparison would get wrong.
        self.assertEqual(
            order_of(row("a", "2024-05-01", "10"), row("b", "2024-05-01", "9")),
            ["b", "a"],
        )


class DateColumnTest(unittest.TestCase):
    """Date is now the only source of a tournament's date (Month/Day/Year are gone)."""

    def test_date_is_zero_padded(self):
        # Dates are compared as strings, so an unpadded date would sort wrong.
        self.assertEqual(TournamentEntry(*row("a", "2024-5-1")).date, "2024-05-01")

    def test_padded_date_is_left_alone(self):
        self.assertEqual(TournamentEntry(*row("a", "2024-05-01")).date, "2024-05-01")

    def test_padded_dates_sort_chronologically_as_strings(self):
        self.assertEqual(
            order_of(row("b", "2024-5-9"), row("a", "2024-05-10")), ["b", "a"]
        )

    def test_unreadable_date_is_kept_not_guessed(self):
        # Better to sort oddly and be spotted than to invent a plausible date.
        self.assertEqual(TournamentEntry(*row("a", "sometime")).date, "sometime")


if __name__ == "__main__":
    unittest.main()
