"""Rebuild the database from results/ (the source of truth).

Runs the rating replay and writes the result into the relational tables. The
whole rebuild happens in one transaction: Player identity is upserted, while the
CurrentRating and TournamentResult projections are truncated and recreated, so a
failed run leaves the previous DB intact and readers never see a half-built one.

This is idempotent — running it twice produces the same DB — which is what makes
"update the database" safe to trigger on every deploy.
"""

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from coco_ratings.pipeline import process_old_results
from coco_ratings.tournaments import TournamentDB

from ratings.models import CurrentRating, Player, Tournament, TournamentResult


class Command(BaseCommand):
    help = "Rebuild the database from the results/ folder (source of truth)."

    def handle(self, *args, **options):
        ratingsdb, _ = process_old_results()
        entries = {
            t.filename: t for t in TournamentDB.read_csv().tournaments if t.filename
        }

        with transaction.atomic():
            # Projections are fully rebuilt; identity (Player) is upserted so
            # rows other tables key off stay stable across rebuilds.
            TournamentResult.objects.all().delete()
            CurrentRating.objects.all().delete()
            Tournament.objects.all().delete()

            players = self._upsert_players(ratingsdb)
            tournaments = self._build_tournaments(ratingsdb, entries)
            self._build_current_ratings(ratingsdb, players)
            self._build_results(ratingsdb, players, tournaments)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt DB: {len(players)} players, {len(tournaments)} tournaments, "
                f"{TournamentResult.objects.count()} results"
            )
        )

    def _upsert_players(self, ratingsdb):
        """Return {name: Player}, upserting identity from the replay."""
        players = {}
        for name, reports in ratingsdb.report.items():
            # coco_id is consistent per name; take it from any report entry.
            coco_id = next(iter(reports.values())).coco_id
            player, _ = Player.objects.update_or_create(
                name=name, defaults={"coco_id": coco_id}
            )
            players[name] = player
        # Drop identity rows for players no longer present anywhere.
        Player.objects.exclude(name__in=players).delete()
        return players

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

    def _build_current_ratings(self, ratingsdb, players):
        CurrentRating.objects.bulk_create(
            CurrentRating(
                player=players[name],
                rating=rec.rating,
                deviation=rec.deviation,
                career_games=rec.games,
                last_played=rec.last_played.date(),
            )
            for name, rec in ratingsdb.players.items()
        )

    def _build_results(self, ratingsdb, players, tournaments):
        TournamentResult.objects.bulk_create(
            TournamentResult(
                player=players[name],
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
            for filename, rep in reports.items()
        )
