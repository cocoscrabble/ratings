"""Read-only views over the ratings projection."""

from django.shortcuts import get_object_or_404, render

from ratings.models import CurrentRating, Player, Tournament, TournamentResult


def ratings_list(request):
    ratings = CurrentRating.objects.select_related("player").order_by(
        "-rating", "player__name"
    )
    return render(request, "ratings/ratings_list.html", {"ratings": ratings})


def player_detail(request, pk):
    player = get_object_or_404(Player, pk=pk)
    current = CurrentRating.objects.filter(player=player).first()
    results = (
        TournamentResult.objects.filter(player=player)
        .select_related("tournament")
        .order_by("-tournament__date", "tournament__filename")
    )
    return render(
        request,
        "ratings/player_detail.html",
        {"player": player, "current": current, "results": results},
    )


def tournament_list(request):
    tournaments = Tournament.objects.order_by("-date", "filename")
    return render(
        request, "ratings/tournament_list.html", {"tournaments": tournaments}
    )


def tournament_detail(request, filename):
    tournament = get_object_or_404(Tournament, filename=filename)
    # Standings order mirrors the engine: wins first, then spread.
    results = (
        TournamentResult.objects.filter(tournament=tournament)
        .select_related("player")
        .order_by("-wins", "-spread")
    )
    return render(
        request,
        "ratings/tournament_detail.html",
        {"tournament": tournament, "results": results},
    )
