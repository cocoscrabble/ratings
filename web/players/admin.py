from django.contrib import admin

from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["player_number", "name", "current_rating"]
    search_fields = ["name", "player_number"]

    @admin.display(description="Current rating")
    def current_rating(self, obj):
        cr = obj.current_rating
        return cr.rating if cr else "—"
