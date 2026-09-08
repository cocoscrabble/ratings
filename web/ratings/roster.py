"""The ``coco.roster/1`` document — the roster Baxter pulls before an event.

One schema, two transports: this builds the document, a view serializes it, and
the same bytes are served whether Baxter fetches ``/api/roster/`` or a human
downloads the snapshot file for an offline event. Keeping the builder separate
from either transport is what makes "identical document" a property of the code
rather than a promise in a plan.

See ``../baxter/plans/PLAN_COCO_PROGRAM.md`` for the contract this satisfies.

**Nothing from ``PlayerDetails`` may appear here.** It is the only private data
this site stores, and this is a bulk export of every player — exactly the kind of
surface ``PlayerDetailsPrivacyTest`` exists to guard. The builder selects fields
explicitly rather than serializing a model, so adding a private field to
``PlayerDetails`` later cannot leak it by default.
"""

import csv
import io
import json
from datetime import UTC

from django.utils import timezone

from players.models import Player

SCHEMA = "coco.roster/1"

# The fields of a roster entry, in order: the JSON keys and the CSV columns are
# the same list, so the two exports cannot describe different players. Adding a
# field to ``_player_row`` without adding it here fails ``roster_csv`` loudly
# (DictWriter rejects unknown keys) rather than silently dropping the column.
FIELDS = (
    "player_number",
    "name",
    "rating",
    "deviation",
    "career_games",
    "last_played",
)


def _player_row(player, rating):
    """One roster entry. ``rating`` is the player's ``CurrentRating`` or None.

    A player with no ``CurrentRating`` has never appeared in a rated result.
    Their rating, deviation and last-played date are genuinely *unknown*, so
    they are null; ``career_games`` is 0, which is a fact rather than an
    absence. Baxter reads the nulls as unrated and lets the calculator seed them
    (1500 / deviation 150), which is the same thing this engine does.
    """
    return {
        # Canonical (zero-padded) by construction — Player.save normalizes.
        "player_number": player.player_number,
        # Display data. Baxter may overwrite its copy on every pull; the number
        # is the only identity.
        "name": player.name,
        "rating": rating.rating if rating else None,
        "deviation": rating.deviation if rating else None,
        "career_games": rating.career_games if rating else 0,
        "last_played": rating.last_played.isoformat() if rating else None,
    }


def build_roster(generated_at=None) -> dict:
    """The whole roster as a plain dict, ready to serialize.

    Ordered by player number so two dumps of the same database are
    byte-identical — which is what lets the snapshot file and the endpoint be
    compared, and what makes a diff between two pulls readable.

    No pagination: the roster is a few hundred rows and a paginated bulk export
    would be more machinery than the problem has.
    """
    players = (
        Player.objects.select_related("computed_rating").order_by("player_number")
    )
    return {
        "schema": SCHEMA,
        "generated_at": (generated_at or timezone.now())
        .astimezone(UTC)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "players": [
            _player_row(p, getattr(p, "computed_rating", None)) for p in players
        ],
    }


def roster_json(generated_at=None) -> str:
    """``build_roster`` serialized. The one serializer both transports use, so
    they cannot disagree about formatting."""
    return json.dumps(build_roster(generated_at), indent=2, ensure_ascii=False)


def roster_csv(generated_at=None) -> str:
    """The same roster as a spreadsheet: a header row and one row per player.

    Built from ``build_roster``, so the CSV and the JSON always list the same
    players in the same order with the same values — it is a rendering of the
    document, not a second source of it.

    It carries the rows only. ``schema`` and ``generated_at`` are document
    metadata with no place in a flat table, and the CSV is not the machine
    contract — Baxter reads the JSON. This is for a human opening the roster in
    a spreadsheet; the date is in the filename.

    Nulls (an unrated player's rating, deviation and last-played date) are
    written as empty cells, which is what a spreadsheet reads as "no value".
    """
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(build_roster(generated_at)["players"])
    return out.getvalue()


def snapshot_filename(generated_at=None, ext="json") -> str:
    """A dated filename, so several downloads do not overwrite each other in a
    downloads folder."""
    stamp = (generated_at or timezone.now()).astimezone(UTC)
    return f"coco-roster-{stamp:%Y%m%d}.{ext}"
