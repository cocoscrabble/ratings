from django.core.validators import RegexValidator
from django.db import models

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
    def current_rating(self):
        return Rating.objects.filter(player=self).order_by("-date").first()


class Rating(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="ratings")
    rating = models.IntegerField()
    date = models.DateField()

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "date"], name="unique_player_date"
            )
        ]

    def __str__(self):
        return f"{self.player.name}: {self.rating} on {self.date}"
