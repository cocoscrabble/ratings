"""Read-only views over the ratings projection."""

import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from accounts.decorators import staff_required
from ratings.models import CurrentRating, Tournament, TournamentResult
from ratings.roster import roster_csv, roster_json, snapshot_filename

# The per-player page lives in the players app (players.views.player_detail),
# which shows both the published rating history and this project's computed
# ratings + tournament results.


def ratings_list(request):
    ratings = CurrentRating.objects.select_related("player").order_by(
        "-rating", "player__name"
    )
    return render(
        request,
        "ratings/ratings_list.html",
        {"ratings": ratings, "section": "ratings"},
    )


def tournament_list(request):
    tournaments = Tournament.objects.order_by("-date", "-order", "filename")
    return render(
        request,
        "ratings/tournament_list.html",
        {"tournaments": tournaments, "section": "tournaments"},
    )


def tournament_detail(request, slug):
    tournament = get_object_or_404(Tournament, filename=slug)
    # Standings order mirrors the engine: wins first, then spread.
    results = (
        TournamentResult.objects.filter(tournament=tournament)
        .select_related("player")
        .order_by("-wins", "-spread")
    )
    return render(
        request,
        "ratings/tournament_detail.html",
        {"tournament": tournament, "results": results, "section": "tournaments"},
    )


def _snapshot_response(body, content_type, ext):
    """A roster body served as a dated attachment."""
    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{snapshot_filename(ext=ext)}"'
    )
    return response


@staff_required
def roster_snapshot(request):
    """Download the ``coco.roster/1`` document as a file.

    The offline half of the roster pull: a director takes this to an event where
    Baxter has no connection here. Baxter reads the file and the (future)
    ``/api/roster/`` endpoint through one code path, and both are produced by
    ``ratings.roster``, so the two cannot drift.

    Staff-only. The individual facts in here are already public — every player
    page shows a name and a rating — but a one-request dump of the entire roster
    is a different thing from a page-at-a-time browse, and the endpoint that
    replaces this will be authenticated too.
    """
    return _snapshot_response(roster_json(), "application/json", "json")


@staff_required
def roster_snapshot_csv(request):
    """The same roster as a spreadsheet.

    For a human: checking the list over, mailing it round, sorting it. Baxter
    reads the JSON, which is the contract; this is a rendering of the same
    ``build_roster`` document, so it is never a second version of the roster.

    Staff-only for the same reason as the JSON — it is the same bulk dump.
    """
    return _snapshot_response(roster_csv(), "text/csv; charset=utf-8", "csv")


def _roster_token_ok(request) -> bool:
    """Whether the request carries the shared roster token.

    ``Authorization: Bearer <token>``, with ``X-Roster-Token: <token>`` accepted
    too — some proxies strip or rewrite Authorization, and this endpoint has to
    work from behind whatever the far end happens to be running.

    Compared with ``compare_digest``. The roster is not sensitive, but a
    timing-safe compare is one line and the alternative is a habit worth not
    forming.

    An unset ``ROSTER_API_TOKEN`` returns False for every request, so a
    misconfigured deploy serves nothing rather than everything.
    """
    expected = settings.ROSTER_API_TOKEN
    if not expected:
        return False
    header = request.headers.get("Authorization", "")
    presented = (
        header[len("Bearer ") :] if header.startswith("Bearer ") else ""
    ) or request.headers.get("X-Roster-Token", "")
    return bool(presented) and secrets.compare_digest(presented, expected)


# csrf_exempt because this is a machine API: CSRF protects *cookie*-
# authenticated state-changing requests, and this is token-authenticated and
# read-only. Without it a POST is rejected by CSRF (403) before require_GET can
# say the useful thing (405), which is a confusing answer to give a client.
@csrf_exempt
@require_GET
def roster_api(request):
    """The ``coco.roster/1`` document over HTTP — the normal path for Baxter.

    Byte-identical to the ``/manage/roster/download/`` file, because both are
    ``ratings.roster.roster_json``; ``test_roster`` asserts that rather than
    trusting it. Baxter reads either through one code path.

    Token-authenticated with a shared static token. The individual facts here
    are already public — every player page shows a name and a rating — so this
    is about not handing a bulk dump to anonymous crawlers, not about guarding
    secrets. **Nothing from PlayerDetails may appear**, which the builder
    enforces by whitelisting fields.

    401 rather than 403: the caller is a machine, and "your credentials were
    wrong" is the useful thing to say. No pagination — the roster is a few
    hundred rows.
    """
    if not _roster_token_ok(request):
        return JsonResponse(
            {"error": "A valid roster token is required."},
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return HttpResponse(roster_json(), content_type="application/json")
