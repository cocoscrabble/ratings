from django.contrib import admin

from .models import Player, PlayerDetails


class PlayerDetailsInline(admin.StackedInline):
    """Edited on the player's own page — it is a 1:1 extension, not its own thing."""

    model = PlayerDetails
    can_delete = False
    # One blank form, ready to type into. Django does not save an untouched
    # form, so a player edited without touching this gets no details row.
    extra = 1
    max_num = 1


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["player_number", "name", "current_rating"]
    search_fields = ["name", "player_number"]
    inlines = [PlayerDetailsInline]

    @admin.display(description="Current rating")
    def current_rating(self, obj):
        cr = obj.current_rating
        return cr.rating if cr else "—"
