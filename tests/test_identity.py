"""The canonical player-number form, shared with Baxter.

These cases are the contract between the two projects: both must agree, or the
same person ends up with two identities. Baxter's own suite asserts the same
table (see ../baxter, PLAN_PLAYER_IDENTITY.md).
"""

import subprocess
import sys
import unittest

from coco_ratings.identity import canonical_player_number


class CanonicalPlayerNumberTest(unittest.TestCase):
    def test_pads_bare_numbers(self):
        self.assertEqual(canonical_player_number("233"), "0233")
        self.assertEqual(canonical_player_number("1"), "0001")

    def test_already_canonical_is_unchanged(self):
        self.assertEqual(canonical_player_number("0233"), "0233")

    def test_over_padded_collapses_onto_the_same_key(self):
        # The int() before zfill is what stops 00233 becoming a third spelling.
        self.assertEqual(canonical_player_number("00233"), "0233")

    def test_accepts_non_strings(self):
        self.assertEqual(canonical_player_number(233), "0233")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(canonical_player_number("  233 "), "0233")

    def test_numbers_wider_than_four_digits_are_not_truncated(self):
        # Nothing should silently lose a digit if the range ever grows.
        self.assertEqual(canonical_player_number("12345"), "12345")

    def test_baxter_placeholder_and_bye_pass_through(self):
        # Baxter mints T- numbers for players the central DB has not issued a
        # number to, and reserves BYE for its synthetic bye opponent. Neither is
        # numeric, and canonicalizing must leave both exactly as they are.
        for value in ("T-7", "T-123", "BYE"):
            with self.subTest(value=value):
                self.assertEqual(canonical_player_number(value), value)

    def test_empty_is_unchanged(self):
        self.assertEqual(canonical_player_number(""), "")

    def test_is_idempotent(self):
        for value in ("233", "0233", "00233", "T-7", "BYE", ""):
            with self.subTest(value=value):
                once = canonical_player_number(value)
                self.assertEqual(canonical_player_number(once), once)

    def test_import_pulls_in_nothing(self):
        # Baxter imports this from a Django app at module import time; it must
        # stay as free of dependencies as coco_ratings.core.
        proc = subprocess.run(
            [sys.executable, "-c",
             "import coco_ratings.identity, sys;"
             "print(','.join(sorted(m for m in sys.modules"
             " if m.startswith('coco_ratings'))))"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(
            sorted(proc.stdout.strip().split(",")),
            ["coco_ratings", "coco_ratings.identity"],
        )
