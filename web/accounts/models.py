"""Site accounts.

A custom user model exists from the start so that later changes — extra
profile fields, or switching the login identity to email — are ordinary
migrations rather than a swap of AUTH_USER_MODEL on a populated database.

Two distinct kinds of account are planned:

* **Staff** (``is_staff``) — the administrators. They own player identity: the
  ``/manage`` section is gated on this flag, not merely on being logged in.
* **Regular users** — not yet built. A person who has an account and, via
  :attr:`User.player`, is linked to the player they are in the ratings.

The link is deliberately *only* a link. It confers no edit rights on the
``Player`` row itself, because ``ratings.build_db`` matches computed players to
``players.Player`` **by name**: a self-service rename would silently orphan that
player's whole tournament history. Name and number stay staff-owned; anything
self-editable belongs on the user, not the player.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    player = models.OneToOneField(
        "players.Player",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="user",
        help_text=(
            "The player in the ratings database this account belongs to. "
            "Optional: staff accounts need not be players."
        ),
    )

    def __str__(self):
        return self.get_username()
