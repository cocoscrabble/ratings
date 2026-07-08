"""Relational projection of the ratings computed from results/.

Everything here is rebuilt by the build_db management command; results/ remains
the source of truth. Player is the stable identity anchor (keyed by name, since
coco_id is a non-unique "9999" placeholder for unknown players). CurrentRating
and TournamentResult are pure projections that build_db truncates and rebuilds.
"""

from django.db import models


class Player(models.Model):
    """A person. The identity anchor other tables point at."""

    # name is the real identity key: the engine dedupes players by name, and
    # coco_id is not unique (unknown players share the "9999" placeholder).
    name = models.CharField(max_length=200, unique=True)
    coco_id = models.CharField(max_length=16, db_index=True)

    def __str__(self):
        return self.name


class Tournament(models.Model):
    """One tournament, from data/tournaments.csv."""

    # filename is the join key / prefix used throughout results/.
    filename = models.CharField(max_length=200, unique=True)
    fancy_name = models.CharField(max_length=300, blank=True)
    division = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=200, blank=True)
    date = models.DateField()

    class Meta:
        ordering = ["date", "filename"]

    def __str__(self):
        return self.fancy_name or self.filename


class CurrentRating(models.Model):
    """A player's latest standing after replaying the whole history (1:1)."""

    player = models.OneToOneField(
        Player, on_delete=models.CASCADE, related_name="current_rating"
    )
    rating = models.IntegerField()
    deviation = models.FloatField()
    career_games = models.IntegerField()
    last_played = models.DateField()

    class Meta:
        ordering = ["-rating"]

    def __str__(self):
        return f"{self.player.name}: {self.rating}"


class TournamentResult(models.Model):
    """A player's before/after numbers and record in one tournament."""

    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="results"
    )
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="results"
    )
    old_rating = models.IntegerField()
    new_rating = models.IntegerField()
    old_deviation = models.FloatField()
    new_deviation = models.FloatField()
    games = models.IntegerField()
    wins = models.FloatField()
    losses = models.FloatField()
    spread = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "tournament"], name="unique_player_tournament"
            )
        ]

    def __str__(self):
        return f"{self.player.name} @ {self.tournament.filename}"
