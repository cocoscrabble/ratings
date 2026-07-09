"""Import / update player identity (name, number) from a CSV file.

Ratings are computed from tournament results (the ratings app) and are not
imported here — this command only maintains the players.Player identity table
that build_db matches computed ratings against.

Usage:
    uv run manage.py import_csv --players players.csv   # columns: player_number,name
    uv run manage.py import_csv --current players.csv   # columns: Name,Number(,Rating ignored)

Flags:
    --update   Update existing player names instead of skipping duplicates.
"""

import csv
import io

from django.core.management.base import BaseCommand, CommandError

from players.models import Player


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


def import_players_rows(rows, update=False):
    """Upsert Player identity from rows (accepts player_number/Number, name/Name)."""
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
            if created:
                imported += 1
            elif update:
                player.name = name
                player.save()
                imported += 1
            else:
                skipped += 1
        except (ValueError, KeyError) as exc:
            errors.append(f"Row {i}: {exc}")
    return imported, skipped, errors


def read_csv_rows(file_path):
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_csv_rows_from_bytes(data):
    text = data.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


class Command(BaseCommand):
    help = "Import / update player identity (name, number) from a CSV file."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--players", metavar="FILE", help="CSV with player_number,name columns"
        )
        group.add_argument(
            "--current", metavar="FILE", help="CSV with Name,Number columns"
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing player names instead of skipping",
        )

    def handle(self, *args, **options):
        path = options["players"] or options["current"]
        rows = read_csv_rows(path)
        imported, skipped, errors = import_players_rows(rows, update=options["update"])
        self.stdout.write(
            f"Players: {imported} imported, {skipped} skipped, {len(errors)} errors"
        )
        for err in errors:
            self.stderr.write(f"  {err}")
        if errors:
            raise CommandError(f"{len(errors)} row(s) had errors (see above).")
