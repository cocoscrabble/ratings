"""Store player_number zero-padded (``1`` -> ``0001``).

Both spellings have always been *accepted* — readers normalize — but exactly
one can be stored, or the string key would split one person into two
identities. This flips the canonical form from bare to padded and brings the
existing rows along.

This must ship in the same deploy as the matching change to
``canonical_player_number``. The release phase runs ``import_csv`` on every
deploy, and that upserts on ``player_number``: if the stored rows and the
normalizer disagreed about the spelling, every player would be duplicated.
"""

from django.db import migrations


def _pad(value):
    value = str(value).strip()
    return str(int(value)).zfill(4) if value.isdigit() else value


def pad_numbers(apps, schema_editor):
    Player = apps.get_model("players", "Player")
    players = list(Player.objects.all())

    # Two rows normalizing to the same key would hit the unique constraint
    # partway through, leaving the table half-converted. Refuse up front and
    # say which rows need a human instead.
    seen = {}
    for player in players:
        seen.setdefault(_pad(player.player_number), []).append(player.player_number)
    clashes = {k: v for k, v in seen.items() if len(v) > 1}
    if clashes:
        raise ValueError(
            f"Cannot pad player numbers: these would collide: {clashes}. "
            "Merge the duplicate players by hand, then re-run."
        )

    changed = [p for p in players if p.player_number != _pad(p.player_number)]
    for player in changed:
        player.player_number = _pad(player.player_number)
    Player.objects.bulk_update(changed, ["player_number"])


def unpad_numbers(apps, schema_editor):
    Player = apps.get_model("players", "Player")
    changed = []
    for player in Player.objects.all():
        bare = str(int(player.player_number)) if player.player_number.isdigit() else None
        if bare is not None and bare != player.player_number:
            player.player_number = bare
            changed.append(player)
    Player.objects.bulk_update(changed, ["player_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0003_remove_rating_unique_player_date_delete_rating"),
    ]

    operations = [
        migrations.RunPython(pad_numbers, unpad_numbers),
    ]
