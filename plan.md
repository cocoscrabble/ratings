# CocoDB Implementation Plan

## Overview

A Django + PostgreSQL web app for managing and searching Scrabble player data.
Deployed via Docker on Dokku.

---

## Tech Stack

- Python 3.13, Django 6.x
- PostgreSQL (via psycopg2), with `pg_trgm` extension for fuzzy search
- Gunicorn (production WSGI server)
- Docker + Dokku for deployment
- Vanilla JS for live search (no framework needed)

---

## Project Structure

```
cocodb/
├── cocodb/                  # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── players/                 # Main Django app
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── management/
│   │   └── commands/
│   │       └── import_csv.py
│   └── templates/
│       └── players/
│           ├── base.html
│           ├── search.html          # public search page
│           ├── player_detail.html
│           ├── manage_base.html     # admin section base
│           ├── manage_import.html
│           ├── manage_players.html
│           └── manage_ratings.html
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── search.js
│   └── img/
│       └── logo.png                 # downloaded from cocoscrabble.org
├── requirements.txt
├── Dockerfile
├── docker-compose.yml               # local dev
└── Procfile                         # Dokku
```

---

## Data Models (`players/models.py`)

### Player
| Field         | Type        | Notes                                        |
|---------------|-------------|----------------------------------------------|
| id            | AutoField   | PK                                           |
| player_number | CharField   | unique, max_length=4, validated: 1-4 digits  |
| name          | CharField   | max_length=200, db_index=True                |

`player_number` is stored as a CharField (to preserve leading zeros if any) but
validated with a regex validator: `r'^\d{1,4}$'`.

### Rating
| Field     | Type         | Notes                              |
|-----------|--------------|------------------------------------|
| id        | AutoField    | PK                                 |
| player    | ForeignKey   | → Player, on_delete=CASCADE        |
| rating    | IntegerField |                                    |
| date      | DateField    |                                    |

- Default ordering on Rating: `['-date']`
- "Current rating" = `Rating.objects.filter(player=p).order_by('-date').first()`
- A player may have zero ratings (newly added, not yet played)
- Unique constraint on `(player, date)` — duplicate entries are skipped on import

---

## Search Strategy

Postgres `pg_trgm` (trigram similarity) for fuzzy name search, enabled via a
migration that runs `CREATE EXTENSION IF NOT EXISTS pg_trgm`.

### Why trigrams
- Handles typos and partial matches (e.g. "smth" → "Smith")
- Works natively in PostgreSQL; Django ships `TrigramSimilarity` in
  `django.contrib.postgres`
- No external search service needed

### Implementation
```python
from django.contrib.postgres.search import TrigramSimilarity

Player.objects.annotate(
    similarity=TrigramSimilarity('name', query)
).filter(
    similarity__gte=0.2
).order_by('-similarity')[:20]
```

Threshold of 0.2 is a starting point; tune after testing with real player names.
A `GistIndex` on `name` using `opclasses=['gist_trgm_ops']` speeds up trigram
queries on large tables.

---

## URL Structure

```
/                          → public search page
/search/                   → search endpoint (JSON or HTML fallback)
/player/<int:pk>/          → player detail (JSON or HTML fallback)

/manage/                   → redirect to /manage/players/
/manage/login/             → login page
/manage/logout/            → logout
/manage/players/           → list all players (50/page)
/manage/players/add/       → add player form
/manage/players/<pk>/edit/ → edit player
/manage/ratings/           → list ratings, filterable by player (50/page)
/manage/ratings/add/       → add rating entry
/manage/ratings/<pk>/edit/ → edit rating entry
/manage/import/            → CSV import page
/manage/import/current/    → import current ratings (Name/Number/Rating, date=today)
```

---

## Views

### Public

**`search_page` (GET `/`)**
- Renders `search.html` with an empty form
- Detects `?q=<query>` for no-JS fallback: runs the search server-side and
  pre-populates the results in the template

**`search_api` (GET `/search/?q=<query>`)**
- Searches player names using trigram similarity (see Search Strategy above)
- Returns JSON: `[{id, player_number, name, current_rating, last_date}, ...]`
- If the request does not include `Accept: application/json`, renders a full
  HTML page with results (no-JS path)
- Limit results to 20

**`player_detail` (GET `/player/<pk>/`)**
- Returns player info + current rating (most recent Rating entry only)
- JSON response for AJAX requests
- HTML page (`player_detail.html`) for direct/no-JS requests
- 404 if player not found

### Admin (all require `@login_required`)

**`manage_players`** — paginated list of all players (50/page), with edit links

**`manage_player_add` / `manage_player_edit`** — ModelForm for Player

**`manage_ratings`** — paginated list of ratings (50/page), filterable by player name

**`manage_rating_add` / `manage_rating_edit`** — ModelForm for Rating

**`manage_import`** — file upload form; on POST, process uploaded CSV
(see CSV Import section)

**`manage_import_current`** — dedicated upload for "current ratings" CSVs
(see "Import Current Ratings" below); date is set to today automatically

---

## Frontend (public page)

### No-JS behaviour
- `<form method="get" action="/search/">` with a text input and "Find Player" button
- Submitting renders a page with matching players and the selected player's details

### JS behaviour (`static/js/search.js`)
1. Attach `input` listener to the search box with 300ms debounce
2. On each debounced input, `fetch('/search/?q=<value>', {headers: {Accept: 'application/json'}})`
3. Display a dropdown list of up to 20 matching player names below the input
4. Clicking a result (or pressing Enter on highlighted item) selects that player
5. "Find Player" button (or selecting from the list) triggers
   `fetch('/player/<id>/')` and populates the details box with:
   - Player Number, Name
   - Current Rating and date of that rating
6. Keyboard navigation (↑/↓/Enter/Escape) on the dropdown

### Design
- Logo from cocoscrabble.org at top of page
- Button style to match cocoscrabble.org (colour, font, border-radius)
- Minimal custom CSS; no heavy framework

---

## CSV Import

### Format
Three supported formats (auto-detected by column headers):

**Players CSV:**
```
player_number,name
1,Alice Smith
```

**Ratings CSV:**
```
player_number,rating,date
1,1450,2025-11-01
```

**Combined CSV:**
```
player_number,name,rating,date
1,Alice Smith,1450,2025-11-01
```

**Current Ratings CSV** (as exported by the organisation — columns: `Name`, `Number`, `Rating`):
```
Name,Number,Rating
Alice Smith,1,1450
Bob Jones,42,1320
```

No `date` column — the import date is set to today (`datetime.date.today()`).
This format upserts both player records and a new Rating row for each player.

`player_number` must be a 1–4 digit integer; rows failing validation are
skipped and reported.

### Management command
```
python manage.py import_csv --players players.csv
python manage.py import_csv --ratings ratings.csv
python manage.py import_csv --combined combined.csv
python manage.py import_csv --current players.csv   # Name/Number/Rating, date=today
```

- `--update` flag: update existing player names by player_number instead of skipping
- Duplicate ratings (same player + date): skipped with a warning
- Prints a summary: rows imported, rows skipped, errors

### Admin upload (`/manage/import/`)
- Standard import form for players/ratings/combined CSVs
- "Import Current Ratings" link leads to `/manage/import/current/`
- Both pages display a summary (and any per-row errors) after processing

### Import Current Ratings (`/manage/import/current/`)
- Dedicated page with a file upload form and explanatory text describing the
  expected `Name,Number,Rating` column format
- On POST:
  1. Parse CSV rows
  2. For each row: upsert the Player (create if new, update name if existing)
  3. Create a Rating entry with `date=datetime.date.today()`, skipping if a
     rating for this player already exists for today
  4. Display import summary

---

## Authentication

- Django's built-in `django.contrib.auth`
- `LoginView` at `/manage/login/` with a simple template
- All `/manage/*` views decorated with `@login_required(login_url='/manage/login/')`
- Superusers created via `manage.py createsuperuser`
- Django admin (`/django-admin/`) also available for direct DB access

---

## Settings

Single `settings.py` using `django-environ` to read from environment variables,
with a `.env` file for local dev:

```
SECRET_KEY=...
DEBUG=True
DATABASE_URL=postgres://user:pass@localhost:5432/cocodb
ALLOWED_HOSTS=localhost,127.0.0.1
STATIC_ROOT=/app/staticfiles
```

Production overrides applied automatically when `DEBUG=False`.

---

## Docker / Dokku

### `Dockerfile`
```
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
CMD ["gunicorn", "cocodb.wsgi", "--bind", "0.0.0.0:8000"]
```

### `docker-compose.yml` (local dev)
- Services: `web` (Django) + `db` (postgres:16)
- Mounts project directory for hot reload with `runserver`

### `Procfile` (Dokku)
```
web: gunicorn cocodb.wsgi --bind 0.0.0.0:$PORT
release: python manage.py migrate
```

Dokku will auto-detect the Postgres plugin and set `DATABASE_URL`.

---

## Implementation Order

1. **Project scaffolding** — `django-admin startproject`, create `players` app,
   set up `requirements.txt`, `.env`, `settings.py`
2. **Models + migrations** — `Player`, `Rating`, enable `pg_trgm` extension,
   add GistIndex; register in `admin.py`
3. **Public search page** — server-side fuzzy search first (no-JS), then add JS layer
4. **Player detail view** — HTML + JSON variants
5. **Design pass** — logo, button styles, CSS
6. **Admin/manage section** — login, player CRUD, rating CRUD
7. **CSV import** — management command first, then admin upload UI
8. **Docker setup** — Dockerfile, docker-compose, Procfile
9. **End-to-end test** — local Docker run against Postgres
