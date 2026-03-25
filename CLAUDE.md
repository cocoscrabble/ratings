# CocoDB

Player data management app for the Coco Scrabble organisation (cocoscrabble.org).

## Tech stack

- Python 3.13, Django 6.x, PostgreSQL
- `uv` for dependency management (`pyproject.toml`, not requirements.txt)
- `ruff` for linting and formatting (configured in `pyproject.toml`, line length 88)
- SQLite for local dev (default), Postgres in production via `DATABASE_URL`
- Deployed via Docker on Dokku

## Running locally

```
cp .env.example .env
uv sync
uv run manage.py migrate
uv run manage.py runserver
```

## Common commands

```
uv run manage.py import_csv --current players.csv   # import Name/Number/Rating CSV
uv run manage.py createsuperuser                     # create admin user
uv run ruff check .                                  # lint
uv run ruff format .                                 # format
```

## Project structure

- `cocodb/` — Django project package (settings, urls, wsgi)
- `players/` — main app: models, views, forms, templates, management commands
- `static/` — CSS, JS, logo image
- `Dockerfile`, `Procfile`, `docker-compose.yml` — deployment config

## Architecture notes

### Models
- `Player` — `player_number` (1-4 digit string, unique), `name` (indexed)
- `Rating` — FK to Player, `rating` (int), `date`; ordered by `-date`; unique constraint on `(player, date)`
- Current rating = most recent Rating row for a player

### Search
- Uses PostgreSQL `pg_trgm` trigram similarity for fuzzy name search (threshold 0.2, GiST index)
- Falls back to `icontains` on SQLite
- The `_with_current_rating()` helper annotates Player querysets with latest rating via `Subquery` to avoid N+1 queries

### URL layout
- `/` — public search page (no-JS fallback via `?q=` and `?player=` params)
- `/search/` — search API (returns JSON when `Accept: application/json`, HTML otherwise)
- `/player/<pk>/` — player detail (JSON or HTML)
- `/manage/` — admin section (login required): player CRUD, rating CRUD, CSV import
- `/manage/import/current/` — dedicated import for the organisation's `Name,Number,Rating` CSV format (date = today)
- `/django-admin/` — Django's built-in admin

### Frontend
- Vanilla JS live search with 300ms debounce, dropdown with keyboard navigation
- No-JS fallback works via standard form GET submission
- Design: light theme, white background, `#cdbaba` header, purple `#531882` buttons matching cocoscrabble.org

### CSV import
- Reusable import functions in `players/management/commands/import_csv.py`
- Used by both the management command (`uv run manage.py import_csv`) and the admin upload UI
- Supports `--players`, `--ratings`, `--combined`, `--current` modes
- `--update` flag upserts player names; duplicate ratings are skipped with warnings

### Templates
- Use `{% load static %}` and `{% static %}` for all asset URLs
- Use `{% url %}` for internal links
- Three base templates: `base.html` (public), `manage_base.html` (admin), `manage_login.html` (standalone)
