from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Tournament-computed ratings (this project's engine projection).
    path("ratings/", include("ratings.urls")),
    # Player database: search + /manage CRUD (home). Keep last (owns "").
    path("", include("players.urls")),
]
