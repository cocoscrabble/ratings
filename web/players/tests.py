from django.test import TestCase

from coco_ratings.paths import PLAYERS_CSV

from players.management.commands.import_csv import import_players_rows, read_csv_rows
from players.models import Player
from players.views import _search_players


class SearchPlayersTest(TestCase):
    """Tests for the _search_players function."""

    @classmethod
    def setUpTestData(cls):
        cls.martin = Player.objects.create(player_number="1", name="Martin DeMello")
        cls.marcia = Player.objects.create(player_number="2", name="Marcia Guthrie")
        cls.marcus = Player.objects.create(player_number="3", name="Marcus Webb")
        cls.alice = Player.objects.create(player_number="4", name="Alice Martin")
        cls.bob = Player.objects.create(player_number="5", name="Bob Smith")

    def _pks(self, query):
        return set(_search_players(query).values_list("pk", flat=True))

    def test_short_query_returns_fuzzy_matches(self):
        """Queries of 4 chars or fewer use normal fuzzy/substring search."""
        results = self._pks("Marc")
        self.assertIn(self.marcia.pk, results)
        self.assertIn(self.marcus.pk, results)

    def test_long_prefix_filters_to_prefix_only(self):
        """A 5+ char query that is a prefix of a first name returns only
        players whose first or last name starts with that prefix."""
        results = self._pks("Marti")
        # "Martin DeMello" — first name starts with "Marti"
        self.assertIn(self.martin.pk, results)
        # "Alice Martin" — last name starts with "Marti"
        self.assertIn(self.alice.pk, results)
        # "Marcia Guthrie" — no word starts with "Marti"
        self.assertNotIn(self.marcia.pk, results)

    def test_long_prefix_matches_last_name(self):
        """Prefix matching works on last names too."""
        results = self._pks("Smith")
        self.assertIn(self.bob.pk, results)
        self.assertEqual(len(results), 1)

    def test_long_prefix_case_insensitive(self):
        """Prefix matching is case-insensitive."""
        results = self._pks("marti")
        self.assertIn(self.martin.pk, results)
        self.assertIn(self.alice.pk, results)

    def test_long_query_no_prefix_falls_through(self):
        """A 5+ char query with no prefix matches falls back to fuzzy search."""
        results = self._pks("Zzzzzzz")
        self.assertEqual(len(results), 0)

    def test_empty_query_returns_nothing(self):
        results = self._pks("")
        self.assertEqual(len(results), 0)


class SeedFileImportTest(TestCase):
    """The checked-in identity file must import cleanly.

    The release phase runs `import_csv --current data/players.csv` on every
    deploy, and a row it rejects raises CommandError — which fails the release
    and aborts the deploy. So a bad row is a broken deploy, and this catches it
    in CI instead.
    """

    def test_checked_in_seed_file_imports_without_errors(self):
        rows = read_csv_rows(PLAYERS_CSV)
        imported, skipped, errors = import_players_rows(rows)

        self.assertEqual(errors, [])
        self.assertEqual(imported, len(rows))
        self.assertEqual(skipped, 0)
        self.assertEqual(Player.objects.count(), len(rows))

    def test_import_is_idempotent(self):
        """Re-running adds nothing: the release phase repeats this every deploy."""
        rows = read_csv_rows(PLAYERS_CSV)
        import_players_rows(rows)
        imported, skipped, errors = import_players_rows(rows)

        self.assertEqual(errors, [])
        self.assertEqual(imported, 0)
        self.assertEqual(skipped, len(rows))
        self.assertEqual(Player.objects.count(), len(rows))

    def test_numbers_are_stored_bare(self):
        """player_number is a string key, so "0233" and "233" are *different*
        players. Prod holds the bare form and it appears in player URLs, so a
        zero-padded seed file would silently duplicate every identity."""
        import_players_rows(read_csv_rows(PLAYERS_CSV))

        padded = Player.objects.filter(player_number__startswith="0")
        self.assertEqual(list(padded), [])
