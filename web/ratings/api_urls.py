"""Machine-facing endpoints.

Kept apart from ``ratings.urls`` (the human-facing rating pages) because the two
have different audiences, different auth and different compatibility promises:
``/api/roster/`` is a contract Baxter codes against, and its shape is pinned by
``../baxter/plans/PLAN_COCO_PROGRAM.md``.
"""

from django.urls import path

from ratings import views

app_name = "api"

urlpatterns = [
    path("roster/", views.roster_api, name="roster"),
]
