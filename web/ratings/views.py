"""Read-only views over the ratings projection."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.decorators import staff_required
from ratings.models import CurrentRating, Tournament, TournamentResult
from ratings.roster import roster_json, snapshot_filename

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
    body = roster_json()
    response = HttpResponse(body, content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="{snapshot_filename()}"'
    )
    return response
