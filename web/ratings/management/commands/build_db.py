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

from coco_ratings.identity import canonical_player_number
from coco_ratings.pipeline import process_old_results
from coco_ratings.tournaments import TournamentDB

from players.models import Player
from ratings.models import CurrentRating, Tournament, TournamentResult


class Command(BaseCommand):
    help = "Rebuild the ratings projection from the results/ folder."

    def handle(self, *args, **options):
        # Standard Django convention: -v 0 means no output at all. That covers
        # the engine's own warnings too, which are otherwise printed straight to
        # stdout and swamp the test runner (tests rebuild several times).
        verbosity = options["verbosity"]
        ratingsdb, _ = process_old_results(quiet=verbosity < 1)
        entries = {
            t.filename: t for t in TournamentDB.read_csv().tournaments if t.filename
        }

        matched, unmatched = self._match_players(ratingsdb)

        with transaction.atomic():
            TournamentResult.objects.all().delete()
            CurrentRating.objects.all().delete()
            Tournament.objects.all().delete()

            tournaments = self._build_tournaments(ratingsdb, entries)
            self._build_current_ratings(ratingsdb, matched)
            self._build_results(ratingsdb, matched, tournaments)

        if verbosity < 1:
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt DB: {len(matched)} players, {len(tournaments)} tournaments, "
                f"{TournamentResult.objects.count()} results"
            )
        )
        keyed = ratingsdb.keyed_by
        self.stdout.write(
            f"Result files: {keyed['name']} name-keyed, {keyed['number']} number-keyed"
        )
        if unmatched:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(unmatched)} rated player(s) with no Player "
                    f"record (add them in /manage, then rebuild):"
                )
            )
            for line in unmatched:
                self.stdout.write(f"  - {line}")

    def _match_players(self, ratingsdb):
        """Join computed players to canonical players.Player rows.

        By number when the result file carried one, by name otherwise. The
        number is preferred because it is unambiguous: matching on names alone
        makes two players who share one into a single player, which is the
        whole reason the number columns exist.

        Nothing is created here — identity is owned by the players app. An
        unmatched player is reported with the key that actually failed, since a
        number with no Player row (someone Baxter knows about and this database
        does not) is a different problem from an unrecognized name (usually a
        typo that has split one player in two).
        """
        rows = list(Player.objects.all())
        by_number = {p.player_number: p for p in rows}
        by_name = {p.name: p for p in rows}

        matched, unmatched = {}, []
        for key, rec in ratingsdb.players.items():
            number = canonical_player_number(rec.number) if rec.number else None
            if number and number in by_number:
                matched[key] = by_number[number]
            elif rec.name in by_name:
                matched[key] = by_name[rec.name]
            elif number:
                unmatched.append(f"{rec.name} (number {number}: no Player record)")
            else:
                unmatched.append(f"{rec.name} (no Player record with that name)")
        return matched, sorted(unmatched)

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
                order=e.sort_order,
            )
        return tournaments

    def _build_current_ratings(self, ratingsdb, matched):
        CurrentRating.objects.bulk_create(
            CurrentRating(
                player=matched[key],
                rating=rec.rating,
                deviation=rec.deviation,
                career_games=rec.games,
                last_played=rec.last_played.date(),
            )
            for key, rec in ratingsdb.players.items()
            if key in matched
        )

    def _build_results(self, ratingsdb, matched, tournaments):
        TournamentResult.objects.bulk_create(
            TournamentResult(
                player=matched[key],
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
            for key, reports in ratingsdb.report.items()
            if key in matched
            for filename, rep in reports.items()
        )
