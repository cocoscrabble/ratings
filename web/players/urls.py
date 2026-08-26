from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from accounts.forms import StaffAuthenticationForm

from ratings import views as ratings_views

from . import views

urlpatterns = [
    # Public
    path("", views.search_page, name="search_page"),
    path("search/", views.search_api, name="search_api"),
    # Player URLs are keyed on the unique player_number; the name-slug is
    # decorative. The bare (slug-less) form redirects to the canonical URL.
    path(
        "player/<int:number>/<slug:slug>/", views.player_detail, name="player_detail"
    ),
    path("player/<int:number>/", views.player_detail, name="player_detail"),
    # Manage
    path("manage/", views.manage_redirect, name="manage_redirect"),
    path(
        "manage/login/",
        LoginView.as_view(
            template_name="players/manage_login.html",
            authentication_form=StaffAuthenticationForm,
        ),
        name="manage_login",
    ),
    path("manage/logout/", LogoutView.as_view(), name="manage_logout"),
    path("manage/players/", views.manage_players, name="manage_players"),
    path(
        "manage/players/add/",
        views.manage_player_add,
        name="manage_player_add",
    ),
    path(
        "manage/players/<int:pk>/edit/",
        views.manage_player_edit,
        name="manage_player_edit",
    ),
    path("manage/import/", views.manage_import, name="manage_import"),
    path("manage/roster/", views.manage_roster, name="manage_roster"),
    # The file itself. Under /manage/ with the page — both so a human finds it
    # where the plan says it is, and so accounts' ManageAccessTest covers its
    # staff gate along with every other manage URL. The *view* stays in the
    # ratings app, which owns the document.
    path(
        "manage/roster/download/",
        ratings_views.roster_snapshot,
        name="manage_roster_download",
    ),
]
