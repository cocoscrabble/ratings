from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

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
        LoginView.as_view(template_name="players/manage_login.html"),
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
]
