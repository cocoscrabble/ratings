"""Read-only views over the ratings projection."""

from django.shortcuts import get_object_or_404, render

from ratings.models import CurrentRating, Tournament, TournamentResult

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
    tournaments = Tournament.objects.order_by("-date", "filename")
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
