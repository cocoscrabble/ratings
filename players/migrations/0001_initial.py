import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Player",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "player_number",
                    models.CharField(
                        max_length=4,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\d{1,4}$",
                                "Player number must be 1\u20134 digits.",
                            )
                        ],
                    ),
                ),
                ("name", models.CharField(db_index=True, max_length=200)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Rating",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ratings",
                        to="players.player",
                    ),
                ),
                ("rating", models.IntegerField()),
                ("date", models.DateField()),
            ],
            options={
                "ordering": ["-date"],
            },
        ),
        migrations.AddConstraint(
            model_name="rating",
            constraint=models.UniqueConstraint(
                fields=["player", "date"], name="unique_player_date"
            ),
        ),
    ]
