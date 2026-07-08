from django.contrib import admin

from ratings.models import CurrentRating, Player, Tournament, TournamentResult


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "coco_id")
    search_fields = ("name", "coco_id")


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("filename", "fancy_name", "date", "city")
    search_fields = ("filename", "fancy_name", "city")
    ordering = ("-date",)


@admin.register(CurrentRating)
class CurrentRatingAdmin(admin.ModelAdmin):
    list_display = ("player", "rating", "deviation", "career_games", "last_played")
    search_fields = ("player__name",)
    ordering = ("-rating",)


@admin.register(TournamentResult)
class TournamentResultAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "tournament",
        "old_rating",
        "new_rating",
        "wins",
        "losses",
        "spread",
    )
    search_fields = ("player__name", "tournament__filename")
    list_filter = ("tournament",)
