from django.db import migrations, models


class SafeTrigramExtension(migrations.RunSQL):
    """Enable pg_trgm on PostgreSQL; no-op on other backends (e.g. SQLite)."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class SafeGistIndex(migrations.RunSQL):
    """Create a GiST trigram index on PostgreSQL; no-op on other backends."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("players", "0001_initial"),
    ]

    operations = [
        SafeTrigramExtension(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql=migrations.RunSQL.noop,
        ),
        SafeGistIndex(
            sql="CREATE INDEX IF NOT EXISTS players_player_name_trgm ON players_player USING GIST (name gist_trgm_ops)",
            reverse_sql="DROP INDEX IF EXISTS players_player_name_trgm",
        ),
    ]
