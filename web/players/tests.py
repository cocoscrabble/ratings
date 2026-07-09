from django.test import TestCase

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
