"""Rebuild the ratings projection from results/ (the source of truth).

Runs the rating replay and writes the computed ratings into the projection
tables (CurrentRating, TournamentResult), keyed to canonical players.Player
rows. Player identity is owned by the players app (CSV import / CRUD); this
command does NOT create players — computed players with no matching Player
record are skipped and reported (add them in /manage, then rebuild).

The rebuild runs in one transaction (truncate + recreate the projections), so a
failed run leaves the previous DB intact. It's idempotent, which is what makes
"update the database" safe to trigger on every deploy.
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from coco_ratings.pipeline import process_old_results
from coco_ratings.tournaments import TournamentDB

from players.models import Player
from ratings.models import CurrentRating, Tournament, TournamentResult


class Command(BaseCommand):
    help = "Rebuild the ratings projection from the results/ folder."

    def handle(self, *args, **options):
        ratingsdb, _ = process_old_results()
        entries = {
            t.filename: t for t in TournamentDB.read_csv().tournaments if t.filename
        }

        # Match computed players to canonical players.Player rows by name.
        players = {p.name: p for p in Player.objects.all()}
        matched = {n: players[n] for n in ratingsdb.players if n in players}
        unmatched = sorted(n for n in ratingsdb.players if n not in players)

        with transaction.atomic():
            TournamentResult.objects.all().delete()
            CurrentRating.objects.all().delete()
            Tournament.objects.all().delete()

            tournaments = self._build_tournaments(ratingsdb, entries)
            self._build_current_ratings(ratingsdb, matched)
            self._build_results(ratingsdb, matched, tournaments)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt DB: {len(matched)} players, {len(tournaments)} tournaments, "
                f"{TournamentResult.objects.count()} results"
            )
        )
        if unmatched:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(unmatched)} rated player(s) with no Player "
                    f"record (add them in /manage, then rebuild):"
                )
            )
            for name in unmatched:
                self.stdout.write(f"  - {name}")

    def _build_tournaments(self, ratingsdb, entries):
        """Return {filename: Tournament} for every processed tournament."""
        seen = {t for reports in ratingsdb.report.values() for t in reports}
        tournaments = {}
        for filename in seen:
            e = entries[filename]
            tournaments[filename] = Tournament.objects.create(
                filename=filename,
                fancy_name=e.fancy_name,
                division=e.division,
                city=e.city,
                date=datetime.strptime(e.date, "%Y-%m-%d").date(),
            )
        return tournaments

    def _build_current_ratings(self, ratingsdb, matched):
        CurrentRating.objects.bulk_create(
            CurrentRating(
                player=matched[name],
                rating=rec.rating,
                deviation=rec.deviation,
                career_games=rec.games,
                last_played=rec.last_played.date(),
            )
            for name, rec in ratingsdb.players.items()
            if name in matched
        )

    def _build_results(self, ratingsdb, matched, tournaments):
        TournamentResult.objects.bulk_create(
            TournamentResult(
                player=matched[name],
                tournament=tournaments[filename],
                old_rating=int(rep.old_rating),
                new_rating=int(rep.new_rating),
                old_deviation=rep.old_deviation,
                new_deviation=rep.new_deviation,
                games=rep.games,
                wins=rep.wins,
                losses=rep.losses,
                spread=rep.spread,
            )
            for name, reports in ratingsdb.report.items()
            if name in matched
            for filename, rep in reports.items()
        )
