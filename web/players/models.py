from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

player_number_validator = RegexValidator(
    r"^\d{1,4}$",
    "Player number must be 1–4 digits.",
)


def canonical_player_number(value):
    """Normalize a player number to the canonical zero-padded form (``0233``).

    The same number is written both ways in practice: bare (``233``) in
    data/players.csv and in URLs, zero-padded (``0233``) in the engine's
    reports and older exports. They mean one player, but ``player_number`` is
    a *string* key, so storing both forms would silently create two
    identities. Everything that creates or looks up a Player normalizes here
    first, so which form is canonical is a storage detail — but there must be
    exactly one, and it is the padded one.

    Note the ``int()`` before padding: it collapses over-padded input
    (``00233``) onto the same key rather than producing a third spelling.
    """
    value = str(value).strip()
    return str(int(value)).zfill(4) if value.isdigit() else value


class Player(models.Model):
    player_number = models.CharField(
        max_length=4,
        unique=True,
        validators=[player_number_validator],
    )
    name = models.CharField(max_length=200, db_index=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        """Normalize on the way in, so the stored key is canonical by construction.

        The form and import_csv both normalize, but ``Player.objects.create``,
        the admin and the shell did not — and one un-normalized write is enough
        to split a person into two identities. (``bulk_create`` still bypasses
        this, as it bypasses ``save`` generally.)
        """
        self.player_number = canonical_player_number(self.player_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (#{self.player_number})"

    @property
    def padded_number(self):
        """Alias for :attr:`player_number`, which is itself padded now.

        Kept because templates and the search JSON both refer to it; dropping
        it would break the JS for no gain.
        """
        return self.player_number

    @property
    def slug(self):
        """Readable name-slug for URLs. Decorative — player_number is the key."""
        return slugify(self.name)

    def get_absolute_url(self):
        # URL is anchored on the unique player_number; the slug is for readability.
        # The URL keeps the bare form even though storage is padded, so every
        # link that already exists stays canonical. Lookups normalize, so both
        # /player/1/ and /player/0001/ resolve to the same player.
        return reverse(
            "player_detail",
            kwargs={"number": int(self.player_number), "slug": self.slug},
        )

    @property
    def current_rating(self):
        """The player's computed rating (ratings.CurrentRating), or None.

        Ratings are the tournament-computed values from the ratings app — the
        single source of truth.
        """
        from ratings.models import CurrentRating

        return CurrentRating.objects.filter(player=self).first()


class PlayerDetails(models.Model):
    """Optional contact and administrative details for a player.

    Separate from :class:`Player` because the two have different lifecycles and
    different audiences. ``Player`` is identity — the name/number pair that
    ``build_db`` matches computed ratings against, re-seeded from
    data/players.csv on every deploy. This is hand-entered admin data that no
    file reproduces: it exists only here, so it is never rewritten by a deploy
    and never rebuilt.

    It is also the first **private** data the site stores. Player pages and the
    search JSON are public, so nothing here may be rendered there — see
    ``PlayerDetailsPrivacyTest``. Editing is via /django-admin/, which is
    superuser-only.

    Every field is optional, so a row may legitimately be entirely blank.
    """

    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name="details",
    )
    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    payout_preference = models.CharField(
        max_length=200,
        blank=True,
        help_text="How this player prefers to be paid out (free text).",
    )
    comments = models.TextField(blank=True)

    class Meta:
        verbose_name = "player details"
        verbose_name_plural = "player details"

    def __str__(self):
        return f"Details for {self.player}"
