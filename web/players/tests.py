from django.test import TestCase

from coco_ratings.paths import PLAYERS_CSV

from players.forms import PlayerForm
from players.management.commands.import_csv import import_players_rows, read_csv_rows
from players.models import Player, canonical_player_number
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

    def test_numbers_are_stored_padded(self):
        """player_number is a string key, so "0233" and "233" would be *different*
        players. Everything normalizes to the padded form on the way in, so the
        seed file (written bare) must land padded and four characters wide."""
        import_players_rows(read_csv_rows(PLAYERS_CSV))

        numbers = Player.objects.values_list("player_number", flat=True)
        self.assertTrue(numbers)
        self.assertEqual({len(n) for n in numbers}, {4})


class PlayerNumberFormTest(TestCase):
    """Either form of the number must resolve to one identity.

    data/players.csv is written bare, but the engine's reports and older exports
    use the zero-padded form, so both get pasted into imports and the /manage
    form. Accepting only one silently creates duplicate players.
    """

    def test_padded_and_bare_rows_import_as_one_player(self):
        imported, _, errors = import_players_rows(
            [{"Name": "Padded Person", "Number": "0233"}]
        )
        self.assertEqual((imported, errors), (1, []))
        self.assertEqual(Player.objects.get().player_number, "0233")

        # The same person written bare must update, not duplicate.
        imported, skipped, errors = import_players_rows(
            [{"Name": "Padded Person", "Number": "233"}]
        )
        self.assertEqual((imported, skipped, errors), (0, 1, []))
        self.assertEqual(Player.objects.count(), 1)

    def test_form_normalizes_padded_input(self):
        form = PlayerForm(data={"player_number": "233", "name": "Padded Person"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().player_number, "0233")

    def test_form_rejects_a_duplicate_written_the_other_way(self):
        """Typing the bare form of an existing padded player is a duplicate,
        not a new person — uniqueness is checked after normalizing."""
        Player.objects.create(player_number="0233", name="Padded Person")
        form = PlayerForm(data={"player_number": "233", "name": "Impostor"})
        self.assertFalse(form.is_valid())
        self.assertIn("player_number", form.errors)

    def test_canonical_player_number(self):
        for raw, expected in [
            ("0233", "0233"),
            ("233", "0233"),
            (" 7 ", "0007"),
            ("00233", "0233"),  # over-padded collapses onto the same key
            ("0000", "0000"),
            ("1234", "1234"),
            ("", ""),  # left alone rather than crashing; the validator rejects it
        ]:
            self.assertEqual(canonical_player_number(raw), expected, raw)

    def test_padded_number_matches_the_stored_key(self):
        """padded_number survives as an alias for templates and the JSON API."""
        p = Player.objects.create(player_number="0233", name="Padded Person")
        self.assertEqual(p.padded_number, "0233")
        self.assertEqual(p.player_number, "0233")

    def test_url_keeps_the_bare_number(self):
        """Storage padded, URLs bare — so links made before the change stay
        canonical and do not start 301-redirecting."""
        p = Player.objects.create(player_number="0233", name="Padded Person")
        self.assertEqual(p.get_absolute_url(), "/player/233/padded-person/")

    def test_both_url_forms_resolve(self):
        Player.objects.create(player_number="0233", name="Padded Person")
        for url in ("/player/233/padded-person/", "/player/0233/padded-person/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_detail_page_shows_padded_number(self):
        Player.objects.create(player_number="0233", name="Padded Person")
        html = self.client.get("/player/233/padded-person/").content.decode()
        self.assertIn("#0233", html)
