"""DB-layer golden check: the projection must match the engine exactly.

Builds the DB with build_db, then asserts every CurrentRating and
TournamentResult row equals what the rating engine computes directly from
results/. This extends the engine's golden-master guarantee across the DB layer.

Computed ratings are keyed to canonical players.Player rows, so the tests seed a
Player per engine player first (build_db matches by name and skips unmatched).
"""

import datetime
import itertools

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from coco_ratings.pipeline import process_old_results
from players.models import Player, canonical_player_number

from ratings.models import CurrentRating, Tournament, TournamentResult


def seed_players(players):
    """Create a canonical players.Player per engine player so build_db matches it.

    Where the corpus carries a number for a player, seed that number: build_db
    matches by number in preference to name, so an invented number that happens
    to equal someone's real one makes two engine records match one Player row
    and the OneToOne CurrentRating insert fails. The invented numbers therefore
    start above every real number in the corpus.
    """
    records = list(players.values())
    real = {int(r.number) for r in records if r.number}
    counter = itertools.count(max(real, default=0) + 1)
    # bulk_create bypasses Player.save(), so normalize explicitly — the stored
    # key must be the padded form or lookups by URL will not find these rows.
    Player.objects.bulk_create(
        Player(
            player_number=canonical_player_number(rec.number or next(counter)),
            name=rec.name,
        )
        for rec in records
    )


class BuildDbTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ratingsdb, _ = process_old_results(quiet=True)
        seed_players(cls.ratingsdb.players)
        call_command("build_db", verbosity=0)

    def test_current_ratings_match_engine(self):
        self.assertEqual(CurrentRating.objects.count(), len(self.ratingsdb.players))
        # Iterate the records, not the keys: a number-keyed player's key is
        # their number, and the Player row is matched on rec.name.
        for rec in self.ratingsdb.players.values():
            cr = CurrentRating.objects.get(player__name=rec.name)
            self.assertEqual(cr.rating, rec.rating, rec.name)
            self.assertAlmostEqual(cr.deviation, rec.deviation, msg=rec.name)
            self.assertEqual(cr.career_games, rec.games, rec.name)
            self.assertEqual(cr.last_played, rec.last_played.date(), rec.name)

    def test_tournament_results_match_engine(self):
        expected = sum(len(reports) for reports in self.ratingsdb.report.values())
        self.assertEqual(TournamentResult.objects.count(), expected)
        # Spot-check one row end to end against the engine's report.
        name = "Dave Wiegand"
        filename, rep = next(iter(self.ratingsdb.report[name].items()))
        tr = TournamentResult.objects.get(
            player__name=name, tournament__filename=filename
        )
        self.assertEqual(tr.new_rating, int(rep.new_rating))
        self.assertEqual(tr.spread, rep.spread)
        self.assertEqual(tr.wins, rep.wins)

    def test_build_db_is_idempotent(self):
        call_command("build_db", verbosity=0)
        self.assertEqual(CurrentRating.objects.count(), len(self.ratingsdb.players))

    def test_skips_players_without_a_record(self):
        # Remove one player's canonical record; rebuild should skip them.
        Player.objects.filter(name="Dave Wiegand").delete()
        call_command("build_db", verbosity=0)
        self.assertFalse(
            CurrentRating.objects.filter(player__name="Dave Wiegand").exists()
        )
        self.assertEqual(
            CurrentRating.objects.count(), len(self.ratingsdb.players) - 1
        )


class ViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ratingsdb, _ = process_old_results(quiet=True)
        seed_players(ratingsdb.players)
        call_command("build_db", verbosity=0)

    def test_ratings_list(self):
        resp = self.client.get(reverse("ratings:ratings_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dave Wiegand")

    def test_ratings_embed(self):
        resp = self.client.get(reverse("ratings:ratings_embed"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dave Wiegand")
        # Just the table: none of the site chrome.
        self.assertNotContains(resp, "site-header")
        # Framable by other sites, unlike the rest of the site.
        self.assertNotIn("X-Frame-Options", resp.headers)
        full = self.client.get(reverse("ratings:ratings_list"))
        self.assertEqual(full.headers["X-Frame-Options"], "DENY")

    def test_player_detail_shows_computed_history(self):
        # The unified player page lives in the players app; URL is number+slug.
        player = Player.objects.get(name="Dave Wiegand")
        resp = self.client.get(player.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tournament history")

    def test_player_url_is_number_and_slug(self):
        player = Player.objects.get(name="Dave Wiegand")
        # Stored padded, linked bare (see Player.get_absolute_url).
        bare = int(player.player_number)
        self.assertEqual(player.get_absolute_url(), f"/player/{bare}/dave-wiegand/")
        # Bare / stale slug 301-redirects to the canonical URL.
        resp = self.client.get(f"/player/{bare}/")
        self.assertRedirects(resp, player.get_absolute_url(), status_code=301)

    def test_tournament_list(self):
        resp = self.client.get(reverse("ratings:tournament_list"))
        self.assertEqual(resp.status_code, 200)

    def test_tournament_detail(self):
        t = Tournament.objects.first()
        assert t is not None
        self.assertEqual(t.get_absolute_url(), f"/ratings/tournament/{t.filename}/")
        resp = self.client.get(t.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Spread")


class TournamentStrTest(TestCase):
    def _tournament(self, **kwargs):
        from datetime import date

        defaults = {"filename": "x", "fancy_name": "Word Cup", "date": date(2022, 1, 1)}
        return Tournament.objects.create(**{**defaults, **kwargs})

    def test_display_name_includes_division(self):
        t = self._tournament(division="D1")
        self.assertEqual(str(t), "Word Cup: D1")

    def test_display_name_without_division(self):
        t = self._tournament(division="")
        self.assertEqual(str(t), "Word Cup")


class DeviationNotShownTest(TestCase):
    """Rating deviation is an internal detail of the rating maths.

    It is stored (Baxter's roster and the admin need it) but no public page
    may show it. The values are distinctive so a leak cannot hide behind a
    coincidental match elsewhere on the page.
    """

    @classmethod
    def setUpTestData(cls):
        cls.player = Player.objects.create(player_number="233", name="Dev Person")
        CurrentRating.objects.create(
            player=cls.player, rating=1800, deviation=123.45,
            career_games=40, last_played=datetime.date(2026, 1, 1),
        )
        cls.tournament = Tournament.objects.create(
            filename="dev-test", fancy_name="Dev Test", date=datetime.date(2026, 1, 1),
        )
        TournamentResult.objects.create(
            player=cls.player, tournament=cls.tournament,
            old_rating=1790, new_rating=1800,
            old_deviation=134.56, new_deviation=123.45,
            games=8, wins=5, losses=3, spread=100,
        )

    def assertNoDeviation(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for value in ("123.45", "134.56", "123.4", "134.6"):
            self.assertNotIn(value, body)
        self.assertNotIn("Deviation", body)

    def test_player_page(self):
        self.assertNoDeviation(self.player.get_absolute_url())

    def test_ratings_list(self):
        self.assertNoDeviation(reverse("ratings:ratings_list"))

    def test_ratings_embed(self):
        self.assertNoDeviation(reverse("ratings:ratings_embed"))

    def test_tournament_page(self):
        self.assertNoDeviation(self.tournament.get_absolute_url())
