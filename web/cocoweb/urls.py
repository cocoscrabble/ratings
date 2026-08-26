from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Tournament-computed ratings (this project's engine projection).
    path("ratings/", include("ratings.urls")),
    # Machine-facing. Its own prefix rather than under /ratings/ because the
    # contract Baxter codes against is "GET /api/roster/", and burying it under
    # a human-facing section would make that URL an accident of layout.
    path("api/", include("ratings.api_urls")),
    # Player database: search + /manage CRUD (home). Keep last (owns "").
    path("", include("players.urls")),
]
