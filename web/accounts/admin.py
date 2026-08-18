from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Stock UserAdmin plus the player link.

    This is the account-management surface: creating staff, resetting a
    forgotten password, and linking an account to its player all happen here.
    """

    list_display = ("username", "email", "player", "is_staff", "is_superuser")
    list_select_related = ("player",)
    autocomplete_fields = ("player",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Ratings database", {"fields": ("player",)}),
    )
