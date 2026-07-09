from django.contrib import admin

from .models import Player, Rating


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 1
    ordering = ["-date"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["player_number", "name", "current_rating"]
    search_fields = ["name", "player_number"]
    inlines = [RatingInline]

    @admin.display(description="Current rating")
    def current_rating(self, obj):
        r = obj.current_rating
        return r.rating if r else "—"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["player", "rating", "date"]
    list_filter = ["date"]
    search_fields = ["player__name", "player__player_number"]
    ordering = ["-date"]
