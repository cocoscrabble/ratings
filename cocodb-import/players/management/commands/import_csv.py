"""
Management command to import player and rating data from CSV files.

Usage:
    uv run manage.py import_csv --players players.csv
    uv run manage.py import_csv --ratings ratings.csv
    uv run manage.py import_csv --combined combined.csv
    uv run manage.py import_csv --current players.csv

Flags:
    --update   Update existing player names instead of skipping duplicates.
"""

import csv
import datetime
import io

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from players.models import Player, Rating


def _parse_player_number(raw):
    """Return cleaned player_number string, or raise ValueError."""
    val = str(raw).strip()
    if not val.isdigit() or not (1 <= len(val) <= 4):
        raise ValueError(f"Invalid player number: {raw!r}")
    return val


def _col(row, *names):
    """Return the first non-empty value found for the given column names."""
    for name in names:
        val = row.get(name, "")
        if val:
            return val
    return ""


# -------------------------------------------------------------------
# Row-level import functions
# -------------------------------------------------------------------


def import_players_rows(rows, update=False):
    imported = skipped = 0
    errors = []
    for i, row in enumerate(rows, start=2):
        try:
            number = _parse_player_number(_col(row, "player_number", "Number"))
            name = _col(row, "name", "Name").strip()
            if not name:
                raise ValueError("Name is empty")
            player, created = Player.objects.get_or_create(
                player_number=number,
                defaults={"name": name},
            )
            if not created:
                if update:
                    player.name = name
                    player.save()
                    imported += 1
                else:
                    skipped += 1
                    continue
            else:
                imported += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"Row {i}: {exc}")
    return imported, skipped, errors


def import_ratings_rows(rows):
    imported = skipped = 0
    errors = []
    for i, row in enumerate(rows, start=2):
        try:
            number = _parse_player_number(_col(row, "player_number", "Number"))
            rating_val = int(_col(row, "rating", "Rating").strip())
            date_str = _col(row, "date", "Date").strip()
            date = datetime.date.fromisoformat(date_str)
            try:
                player = Player.objects.get(player_number=number)
            except Player.DoesNotExist:
                errors.append(f"Row {i}: player #{number} not found")
                skipped += 1
                continue
            _, created = Rating.objects.get_or_create(
                player=player, date=date, defaults={"rating": rating_val}
            )
            if created:
                imported += 1
            else:
                skipped += 1
                errors.append(f"Row {i}: duplicate rating for #{number} on {date}")
        except (ValueError, KeyError) as exc:
            errors.append(f"Row {i}: {exc}")
    return imported, skipped, errors


def import_combined_rows(rows, update=False):
    """Import rows that have both player and rating columns."""
    p_imported = p_skipped = r_imported = r_skipped = 0
    errors = []
    for i, row in enumerate(rows, start=2):
        try:
            number = _parse_player_number(_col(row, "player_number", "Number"))
            name = _col(row, "name", "Name").strip()
            rating_val = int(_col(row, "rating", "Rating").strip())
            date_str = _col(row, "date", "Date").strip()
            date = datetime.date.fromisoformat(date_str)

            player, created = Player.objects.get_or_create(
                player_number=number, defaults={"name": name}
            )
            if not created and update:
                player.name = name
                player.save()
            if created:
                p_imported += 1
            else:
                p_skipped += 1

            _, r_created = Rating.objects.get_or_create(
                player=player, date=date, defaults={"rating": rating_val}
            )
            if r_created:
                r_imported += 1
            else:
                r_skipped += 1
                errors.append(f"Row {i}: duplicate rating for #{number} on {date}")
        except (ValueError, KeyError, IntegrityError) as exc:
            errors.append(f"Row {i}: {exc}")
    return p_imported, p_skipped, r_imported, r_skipped, errors


def import_current_rows(rows, update=True):
    """Import Name/Number/Rating rows; date is set to today.

    Always upserts player records (update=True by default).
    """
    today = datetime.date.today()
    p_imported = p_skipped = r_imported = r_skipped = 0
    errors = []
    for i, row in enumerate(rows, start=2):
        try:
            number = _parse_player_number(_col(row, "Number", "player_number"))
            name = _col(row, "Name", "name").strip()
            rating_val = int(_col(row, "Rating", "rating").strip())
            if not name:
                raise ValueError("Name is empty")

            player, created = Player.objects.get_or_create(
                player_number=number, defaults={"name": name}
            )
            if not created and update:
                player.name = name
                player.save()
            if created:
                p_imported += 1
            else:
                p_skipped += 1

            _, r_created = Rating.objects.get_or_create(
                player=player, date=today, defaults={"rating": rating_val}
            )
            if r_created:
                r_imported += 1
            else:
                r_skipped += 1
                errors.append(
                    f"Row {i}: rating for #{number} on {today} already exists"
                )
        except (ValueError, KeyError, IntegrityError) as exc:
            errors.append(f"Row {i}: {exc}")
    return p_imported, p_skipped, r_imported, r_skipped, errors


def read_csv_rows(file_path):
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_csv_rows_from_bytes(data):
    text = data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


# -------------------------------------------------------------------
# Management command
# -------------------------------------------------------------------


class Command(BaseCommand):
    help = "Import player and rating data from CSV files"

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--players",
            metavar="FILE",
            help="CSV with player_number,name columns",
        )
        group.add_argument(
            "--ratings",
            metavar="FILE",
            help="CSV with player_number,rating,date columns",
        )
        group.add_argument(
            "--combined",
            metavar="FILE",
            help="CSV with player_number,name,rating,date columns",
        )
        group.add_argument(
            "--current",
            metavar="FILE",
            help="CSV with Name,Number,Rating; date set to today",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing player names instead of skipping",
        )

    def handle(self, *args, **options):
        update = options["update"]
        errors = []

        if options["players"]:
            rows = read_csv_rows(options["players"])
            imported, skipped, errors = import_players_rows(rows, update=update)
            self.stdout.write(
                f"Players: {imported} imported, {skipped} skipped, {len(errors)} errors"
            )

        elif options["ratings"]:
            rows = read_csv_rows(options["ratings"])
            imported, skipped, errors = import_ratings_rows(rows)
            self.stdout.write(
                f"Ratings: {imported} imported, {skipped} skipped, {len(errors)} errors"
            )

        elif options["combined"]:
            rows = read_csv_rows(options["combined"])
            pi, ps, ri, rs, errors = import_combined_rows(rows, update=update)
            self.stdout.write(
                f"Players: {pi} imported, {ps} skipped  |  "
                f"Ratings: {ri} imported, {rs} skipped  |  "
                f"{len(errors)} errors"
            )

        elif options["current"]:
            rows = read_csv_rows(options["current"])
            pi, ps, ri, rs, errors = import_current_rows(rows, update=update)
            today = datetime.date.today()
            self.stdout.write(
                f"Current ratings ({today}): "
                f"Players {pi} imported/{ps} skipped  |  "
                f"Ratings {ri} imported/{rs} skipped  |  "
                f"{len(errors)} errors"
            )

        for err in errors:
            self.stderr.write(f"  {err}")

        if errors:
            raise CommandError(f"{len(errors)} row(s) had errors (see above).")
