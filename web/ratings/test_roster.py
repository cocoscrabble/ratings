"""The ``coco.roster/1`` document and its snapshot download.

The roster is a bulk export of every player, which makes it the widest surface
the site has — so the privacy guard here matters more than on any single page.
"""

import json
from datetime import date, datetime, timezone as dt_timezone

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from players.models import Player, PlayerDetails

from ratings.models import CurrentRating
from ratings.roster import SCHEMA, build_roster, roster_json, snapshot_filename


class RosterDocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rated = Player.objects.create(player_number="233", name="Alec Sjöholm")
        CurrentRating.objects.create(
            player=cls.rated,
            rating=2093,
            deviation=76.92,
            career_games=489,
            last_played=date(2026, 3, 14),
        )
        cls.unrated = Player.objects.create(player_number="7", name="New Nellie")

    def _by_number(self):
        return {p["player_number"]: p for p in build_roster()["players"]}

    def test_the_envelope(self):
        doc = build_roster(
            generated_at=datetime(2026, 8, 22, 14, 3, tzinfo=dt_timezone.utc)
        )
        self.assertEqual(doc["schema"], SCHEMA)
        self.assertEqual(doc["generated_at"], "2026-08-22T14:03:00Z")
        self.assertEqual(len(doc["players"]), 2)

    def test_a_rated_player_carries_all_four_rating_fields(self):
        row = self._by_number()["0233"]
        self.assertEqual(
            row,
            {
                "player_number": "0233",
                "name": "Alec Sjöholm",
                "rating": 2093,
                "deviation": 76.92,
                "career_games": 489,
                "last_played": "2026-03-14",
            },
        )

    def test_an_unrated_player_has_a_null_rating(self):
        row = self._by_number()["0007"]
        self.assertIsNone(row["rating"])
        self.assertIsNone(row["deviation"])
        self.assertIsNone(row["last_played"])
        # Zero games is a fact, not an absence — they have played none.
        self.assertEqual(row["career_games"], 0)

    def test_numbers_are_canonical(self):
        """Baxter keys on this, and 7 and 0007 must not be two people."""
        self.assertEqual(
            sorted(self._by_number()), ["0007", "0233"]
        )

    def test_the_order_is_stable(self):
        """Two dumps of the same database must be byte-identical, so a diff
        between two pulls is readable and the file and the endpoint can be
        compared."""
        stamp = datetime(2026, 8, 22, 14, 3, tzinfo=dt_timezone.utc)
        self.assertEqual(roster_json(stamp), roster_json(stamp))
        numbers = [p["player_number"] for p in build_roster()["players"]]
        self.assertEqual(numbers, sorted(numbers))

    def test_it_serializes_to_valid_json_with_names_intact(self):
        doc = json.loads(roster_json())
        names = [p["name"] for p in doc["players"]]
        self.assertIn("Alec Sjöholm", names)

    def test_the_filename_is_dated(self):
        stamp = datetime(2026, 8, 22, 14, 3, tzinfo=dt_timezone.utc)
        self.assertEqual(snapshot_filename(stamp), "coco-roster-20260822.json")

    def test_a_roster_with_no_players_is_still_a_valid_document(self):
        Player.objects.all().delete()
        doc = build_roster()
        self.assertEqual(doc["schema"], SCHEMA)
        self.assertEqual(doc["players"], [])


class RosterPrivacyTests(TestCase):
    """Nothing from PlayerDetails may appear in the roster.

    It is the only private data this site holds, and this export is every
    player in one request — the widest surface there is. ``build_roster``
    selects fields explicitly rather than serializing a model, so a private
    field added later cannot leak by default; this is what proves it.
    """

    SECRETS = {
        "country": "Canada",
        "state": "Ontario",
        "city": "Toronto",
        "email": "player@example.com",
        "phone_number": "+1 416 555 0134",
        "payout_preference": "e-transfer",
        "comments": "Prefers afternoon rounds.",
    }

    @classmethod
    def setUpTestData(cls):
        cls.player = Player.objects.create(player_number="233", name="Padded Person")
        PlayerDetails.objects.create(player=cls.player, **cls.SECRETS)

    def test_the_document_leaks_nothing(self):
        body = roster_json()
        for field, value in self.SECRETS.items():
            with self.subTest(field=field):
                self.assertNotIn(value, body)
                self.assertNotIn(field, body)

    def test_a_roster_row_has_exactly_the_contracted_keys(self):
        """A whitelist, so a new model field cannot widen the document."""
        row = build_roster()["players"][0]
        self.assertEqual(
            set(row),
            {
                "player_number", "name", "rating", "deviation",
                "career_games", "last_played",
            },
        )


class RosterSnapshotViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.player = Player.objects.create(player_number="233", name="Alec")
        cls.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        cls.plain = User.objects.create_user(username="plain", password="pw")

    def _url(self):
        return reverse("manage_roster_download")

    def test_staff_download_serves_the_document_as_a_file(self):
        self.client.force_login(self.staff)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("coco-roster-", response["Content-Disposition"])
        doc = json.loads(response.content)
        self.assertEqual(doc["schema"], SCHEMA)
        self.assertEqual(doc["players"][0]["player_number"], "0233")

    def test_the_download_is_the_builder_verbatim(self):
        """The file and the (future) endpoint are the same bytes because both go
        through ``roster_json`` — asserted here so a view that starts building
        its own payload fails."""
        self.client.force_login(self.staff)
        body = self.client.get(self._url()).content.decode()
        self.assertEqual(
            json.loads(body)["players"], json.loads(roster_json())["players"]
        )

    def test_it_is_not_public(self):
        """Every fact in here is on a public page already, but a one-request dump
        of the whole roster is a different thing from browsing it."""
        response = self.client.get(self._url())
        self.assertNotEqual(response.status_code, 200)

    def test_a_non_staff_user_cannot_download_it(self):
        self.client.force_login(self.plain)
        response = self.client.get(self._url())
        self.assertNotEqual(response.status_code, 200)


class ManageRosterPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        cls.rated = Player.objects.create(player_number="1", name="Rated Rita")
        CurrentRating.objects.create(
            player=cls.rated, rating=1800, deviation=50.0,
            career_games=100, last_played=date(2026, 1, 1),
        )
        Player.objects.create(player_number="2", name="Unrated Una")

    def test_it_counts_players_and_links_the_download(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("manage_roster"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["player_count"], 2)
        self.assertEqual(response.context["rated_count"], 1)
        self.assertContains(response, reverse("manage_roster_download"))

    def test_it_is_staff_only(self):
        response = self.client.get(reverse("manage_roster"))
        self.assertNotEqual(response.status_code, 200)
