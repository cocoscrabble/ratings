"""Player identity: the canonical form of a CoCo player number.

Shared deliberately. Baxter (``../baxter``, the tournament manager) keys players
by ``player_number`` too, and the two systems exchange rosters and results by
that key. If each had its own idea of whether ``233`` and ``0233`` are the same
person, they would eventually disagree — and disagreeing about identity is the
one failure that quietly splits a person in two on both sides at once. So this
lives in the shipped package rather than in the web app, and both projects
import it.

Dependency-free, like ``coco_ratings.core``: importable from a Django app, a
tournament manager, or a script, without dragging anything along.
"""

# Baxter also mints local placeholder numbers (``T-7``) for players the central
# database has not issued a number to yet, and reserves ``BYE`` for its
# synthetic bye opponent. Neither is a CoCo number, and neither is digits, so
# both fall through the ``isdigit()`` check below unchanged — which is the
# behaviour Baxter relies on. Keep it that way: canonicalizing must never
# rewrite a non-numeric key.


def canonical_player_number(value):
    """Normalize a player number to the canonical zero-padded form (``0233``).

    The same number is written both ways in practice: bare (``233``) in
    data/players.csv and in URLs, zero-padded (``0233``) in the engine's
    reports and older exports. They mean one player, but ``player_number`` is
    a *string* key, so storing both forms would silently create two
    identities. Everything that creates or looks up a Player normalizes here
    first, so which form is canonical is a storage detail — but there must be
    exactly one, and it is the padded one.

    Note the ``int()`` before padding: it collapses over-padded input
    (``00233``) onto the same key rather than producing a third spelling.

    Non-numeric values (Baxter's ``T-7`` placeholders, ``BYE``) pass through
    untouched.
    """
    value = str(value).strip()
    return str(int(value)).zfill(4) if value.isdigit() else value
