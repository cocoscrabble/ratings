"""Relational projection of the ratings computed from results/.

Everything here is rebuilt by the build_db management command; results/ remains
the source of truth. Player identity lives in the players app (players.Player);
CurrentRating and TournamentResult are pure projections keyed to it, which
build_db truncates and rebuilds (matching engine output to players by name).
"""

from django.db import models


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
        name = self.fancy_name or self.filename
        if self.division:
            return f"{name}: {self.division}"
        return name


class CurrentRating(models.Model):
    """A player's latest standing after replaying the whole history (1:1)."""

    # related_name avoids clashing with players.Player.current_rating (the
    # published-rating property); this is the *computed* rating.
    player = models.OneToOneField(
        "players.Player", on_delete=models.CASCADE, related_name="computed_rating"
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
        "players.Player", on_delete=models.CASCADE, related_name="tournament_results"
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

    @property
    def rating_change(self):
        return self.new_rating - self.old_rating

    @property
    def record(self):
        """Win-loss record, e.g. "6-1" or "3.5-3.5" (ties count as half)."""

        def fmt(x):
            return str(int(x)) if x == int(x) else str(x)

        return f"{fmt(self.wins)}-{fmt(self.losses)}"

    def __str__(self):
        return f"{self.player.name} @ {self.tournament.filename}"
