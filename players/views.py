from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Player


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def _search_players(query):
    """Return a queryset of players matching query, using trigram on Postgres
    and icontains on other backends (e.g. SQLite in local dev)."""
    if not query:
        return Player.objects.none()
    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import TrigramSimilarity

        return (
            Player.objects.annotate(similarity=TrigramSimilarity("name", query))
            .filter(similarity__gte=0.2)
            .order_by("-similarity")[:20]
        )
    return Player.objects.filter(name__icontains=query).order_by("name")[:20]


def _player_data(player):
    """Serialise a player + current rating to a dict."""
    cr = player.current_rating
    return {
        "id": player.pk,
        "player_number": player.player_number,
        "name": player.name,
        "current_rating": cr.rating if cr else None,
        "rating_date": cr.date.isoformat() if cr else None,
    }


def _wants_json(request):
    return "application/json" in request.META.get("HTTP_ACCEPT", "")


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------


def search_page(request):
    """Main search page. Handles no-JS fallback via ?q= query param."""
    query = request.GET.get("q", "").strip()
    players = _search_players(query) if query else []
    selected = None

    player_id = request.GET.get("player")
    if player_id:
        try:
            selected = Player.objects.get(pk=player_id)
        except Player.DoesNotExist:
            pass

    return render(
        request,
        "players/search.html",
        {"query": query, "players": players, "selected": selected},
    )


def search_api(request):
    """Search endpoint — returns JSON for AJAX, HTML page for no-JS."""
    query = request.GET.get("q", "").strip()
    players = _search_players(query)

    if _wants_json(request):
        return JsonResponse([_player_data(p) for p in players], safe=False)

    return render(
        request,
        "players/search.html",
        {"query": query, "players": players, "selected": None},
    )


def player_detail(request, pk):
    """Player detail — returns JSON for AJAX, HTML for direct/no-JS."""
    player = get_object_or_404(Player, pk=pk)

    if _wants_json(request):
        return JsonResponse(_player_data(player))

    return render(request, "players/player_detail.html", {"player": player})


# ---------------------------------------------------------------------------
# Manage views (login required) — stubs, expanded in later commits
# ---------------------------------------------------------------------------


@login_required
def manage_redirect(request):
    return redirect("manage_players")


@login_required
def manage_players(request):
    return render(request, "players/manage_players.html", {})


@login_required
def manage_ratings(request):
    return render(request, "players/manage_ratings.html", {})


@login_required
def manage_import(request):
    return render(request, "players/manage_import.html", {})


@login_required
def manage_import_current(request):
    return render(request, "players/manage_import_current.html", {})
