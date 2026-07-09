"""DB-layer golden check: the projection must match the engine exactly.

Builds the DB with build_db, then asserts every CurrentRating and
TournamentResult row equals what the rating engine computes directly from
results/. This extends the engine's golden-master guarantee across the DB layer.
"""

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from coco_ratings.pipeline import process_old_results

from ratings.models import CurrentRating, Player, Tournament, TournamentResult


class BuildDbTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("build_db", verbosity=0)
        cls.ratingsdb, _ = process_old_results()

    def test_players_match_engine(self):
        self.assertEqual(Player.objects.count(), len(self.ratingsdb.players))

    def test_current_ratings_match_engine(self):
        self.assertEqual(CurrentRating.objects.count(), len(self.ratingsdb.players))
        for name, rec in self.ratingsdb.players.items():
            cr = CurrentRating.objects.get(player__name=name)
            self.assertEqual(cr.rating, rec.rating, name)
            self.assertAlmostEqual(cr.deviation, rec.deviation, msg=name)
            self.assertEqual(cr.career_games, rec.games, name)
            self.assertEqual(cr.last_played, rec.last_played.date(), name)

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


class ViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("build_db", verbosity=0)

    def test_ratings_list(self):
        resp = self.client.get(reverse("ratings:ratings_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dave Wiegand")

    def test_player_detail(self):
        player = Player.objects.get(name="Dave Wiegand")
        resp = self.client.get(reverse("ratings:player_detail", args=[player.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tournament history")

    def test_tournament_list(self):
        resp = self.client.get(reverse("ratings:tournament_list"))
        self.assertEqual(resp.status_code, 200)

    def test_tournament_detail(self):
        t = Tournament.objects.first()
        assert t is not None
        resp = self.client.get(reverse("ratings:tournament_detail", args=[t.filename]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Spread")

    def test_unknown_player_404(self):
        resp = self.client.get(reverse("ratings:player_detail", args=[999999]))
        self.assertEqual(resp.status_code, 404)


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
