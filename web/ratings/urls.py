from django.urls import path

from ratings import views

app_name = "ratings"

urlpatterns = [
    path("", views.ratings_list, name="ratings_list"),
    path("tournaments/", views.tournament_list, name="tournament_list"),
    path("tournament/<slug:slug>/", views.tournament_detail, name="tournament_detail"),
]
