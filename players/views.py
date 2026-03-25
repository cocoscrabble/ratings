import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import DateField, IntegerField, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PlayerForm, RatingForm
from .models import Player, Rating

# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _with_current_rating(qs):
    """Annotate a Player queryset with latest rating fields in a single query."""
    latest = Rating.objects.filter(player=OuterRef("pk")).order_by("-date")
    return qs.annotate(
        latest_rating=Subquery(
            latest.values("rating")[:1], output_field=IntegerField()
        ),
        latest_rating_date=Subquery(
            latest.values("date")[:1], output_field=DateField()
        ),
    )


def _search_players(query):
    """Search players by name. On Postgres, combines substring matches with
    trigram fuzzy matches so short queries and typos both work well.
    Falls back to icontains on SQLite."""
    if not query:
        return Player.objects.none()
    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import TrigramWordSimilarity

        # Exact substring matches (always reliable)
        exact = set(
            Player.objects.filter(name__icontains=query).values_list("pk", flat=True)[
                :20
            ]
        )
        # Fuzzy matches via trigram word similarity
        fuzzy = set(
            Player.objects.annotate(similarity=TrigramWordSimilarity(query, "name"))
            .filter(similarity__gte=0.15)
            .values_list("pk", flat=True)[:20]
        )
        combined_pks = exact | fuzzy
        if not combined_pks:
            return _with_current_rating(Player.objects.none())
        qs = (
            Player.objects.filter(pk__in=combined_pks)
            .annotate(similarity=TrigramWordSimilarity(query, "name"))
            .order_by("-similarity", "name")[:20]
        )
    else:
        qs = Player.objects.filter(name__icontains=query).order_by("name")[:20]
    return _with_current_rating(qs)


def _player_data(player):
    """Serialise a player + current rating to a dict.

    Works with both annotated querysets (latest_rating/latest_rating_date)
    and plain Player instances (falls back to current_rating property).
    """
    if hasattr(player, "latest_rating"):
        rating = player.latest_rating
        date = player.latest_rating_date
    else:
        cr = player.current_rating
        rating = cr.rating if cr else None
        date = cr.date if cr else None
    return {
        "id": player.pk,
        "player_number": player.player_number,
        "name": player.name,
        "current_rating": rating,
        "rating_date": date.isoformat() if date else None,
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
# Manage views (login required)
# ---------------------------------------------------------------------------

MANAGE_PAGE_SIZE = 50


@login_required
def manage_redirect(request):
    return redirect("manage_players")


@login_required
def manage_players(request):
    qs = _with_current_rating(Player.objects.all())
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(name__icontains=query)
    paginator = Paginator(qs, MANAGE_PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "players/manage_players.html",
        {"page_obj": page, "query": query},
    )


@login_required
def manage_player_add(request):
    form = PlayerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Player added.")
        return redirect("manage_players")
    return render(
        request, "players/manage_player_form.html", {"form": form, "action": "Add"}
    )


@login_required
def manage_player_edit(request, pk):
    player = get_object_or_404(Player, pk=pk)
    form = PlayerForm(request.POST or None, instance=player)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Player updated.")
        return redirect("manage_players")
    return render(
        request,
        "players/manage_player_form.html",
        {"form": form, "action": "Edit", "player": player},
    )


@login_required
def manage_ratings(request):
    qs = Rating.objects.select_related("player").all()
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(player__name__icontains=query)
    paginator = Paginator(qs, MANAGE_PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "players/manage_ratings.html",
        {"page_obj": page, "query": query},
    )


@login_required
def manage_rating_add(request):
    form = RatingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rating added.")
        return redirect("manage_ratings")
    return render(
        request, "players/manage_rating_form.html", {"form": form, "action": "Add"}
    )


@login_required
def manage_rating_edit(request, pk):
    rating = get_object_or_404(Rating, pk=pk)
    form = RatingForm(request.POST or None, instance=rating)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rating updated.")
        return redirect("manage_ratings")
    return render(
        request,
        "players/manage_rating_form.html",
        {"form": form, "action": "Edit", "rating": rating},
    )


@login_required
def manage_import(request):
    from players.management.commands.import_csv import (
        import_combined_rows,
        import_players_rows,
        import_ratings_rows,
        read_csv_rows_from_bytes,
    )

    summary = None
    if request.method == "POST":
        mode = request.POST.get("mode", "players")
        uploaded = request.FILES.get("csv_file")
        if not uploaded:
            messages.error(request, "Please select a file to upload.")
        else:
            rows = read_csv_rows_from_bytes(uploaded.read())
            update = "update" in request.POST

            if mode == "players":
                imp, skp, errors = import_players_rows(rows, update=update)
                summary = {
                    "mode": "Players",
                    "lines": [f"{imp} imported, {skp} skipped"],
                    "errors": errors,
                }
            elif mode == "ratings":
                imp, skp, errors = import_ratings_rows(rows)
                summary = {
                    "mode": "Ratings",
                    "lines": [f"{imp} imported, {skp} skipped"],
                    "errors": errors,
                }
            elif mode == "combined":
                pi, ps, ri, rs, errors = import_combined_rows(rows, update=update)
                summary = {
                    "mode": "Combined",
                    "lines": [
                        f"Players: {pi} imported, {ps} skipped",
                        f"Ratings: {ri} imported, {rs} skipped",
                    ],
                    "errors": errors,
                }
            else:
                messages.error(request, f"Unknown import mode: {mode}")

    return render(request, "players/manage_import.html", {"summary": summary})


@login_required
def manage_import_current(request):
    from players.management.commands.import_csv import (
        import_current_rows,
        read_csv_rows_from_bytes,
    )

    summary = None
    if request.method == "POST":
        uploaded = request.FILES.get("csv_file")
        if not uploaded:
            messages.error(request, "Please select a file to upload.")
        else:
            rows = read_csv_rows_from_bytes(uploaded.read())
            pi, ps, ri, rs, errors = import_current_rows(rows)
            today = datetime.date.today()
            summary = {
                "mode": f"Current Ratings ({today})",
                "lines": [
                    f"Players: {pi} imported, {ps} updated",
                    f"Ratings: {ri} imported, {rs} skipped (already existed for today)",
                ],
                "errors": errors,
            }

    return render(request, "players/manage_import_current.html", {"summary": summary})
