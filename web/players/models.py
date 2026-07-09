from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

player_number_validator = RegexValidator(
    r"^\d{1,4}$",
    "Player number must be 1–4 digits.",
)


class Player(models.Model):
    player_number = models.CharField(
        max_length=4,
        unique=True,
        validators=[player_number_validator],
    )
    name = models.CharField(max_length=200, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (#{self.player_number})"

    @property
    def slug(self):
        """Readable name-slug for URLs. Decorative — player_number is the key."""
        return slugify(self.name)

    def get_absolute_url(self):
        # URL is anchored on the unique player_number; the slug is for readability.
        return reverse(
            "player_detail",
            kwargs={"number": self.player_number, "slug": self.slug},
        )

    @property
    def current_rating(self):
        """The player's computed rating (ratings.CurrentRating), or None.

        Ratings are the tournament-computed values from the ratings app — the
        single source of truth.
        """
        from ratings.models import CurrentRating

        return CurrentRating.objects.filter(player=self).first()
