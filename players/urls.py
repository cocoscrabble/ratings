from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    # Public
    path("", views.search_page, name="search_page"),
    path("search/", views.search_api, name="search_api"),
    path("player/<int:pk>/", views.player_detail, name="player_detail"),
    # Manage
    path("manage/", views.manage_redirect, name="manage_redirect"),
    path(
        "manage/login/",
        LoginView.as_view(template_name="players/manage_login.html"),
        name="manage_login",
    ),
    path("manage/logout/", LogoutView.as_view(), name="manage_logout"),
    path("manage/players/", views.manage_players, name="manage_players"),
    path("manage/ratings/", views.manage_ratings, name="manage_ratings"),
    path("manage/import/", views.manage_import, name="manage_import"),
    path("manage/import/current/", views.manage_import_current, name="manage_import_current"),
]
