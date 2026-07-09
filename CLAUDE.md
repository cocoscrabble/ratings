# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Rating software for CoCo (crossword game) tournaments. Ratings use the Norwegian
rating system (spread-based Glicko-style; see `docs/norwegian-rating.pdf`). There
is no database yet — everything is CSV/text files carried forward by re-running
the full tournament history from scratch each time.

## Project layout

`src`-layout package installed with **uv**:

```
pyproject.toml          # project metadata + console script + ruff config
uv.lock
src/coco_ratings/       # the importable package
    types.py            # data model: Player, Section, GameResult, constants
    io.py               # file readers/writers (CSV/TSV, .tou, .RT) + parsing
    rating.py           # engine (RatingsCalculator), Tournament, PlayerList, CLI
    gui.py              # Tk widgets + base App/SimulationApp (imports nothing heavy)
    gui_app.py          # GUI apps wiring Tk to the pipeline (keeps pipeline Tk-free)
    ratingsdb.py        # RatingsDB (carry-forward replay), PlayerRecord/PlayerReport
    reports.py          # pure output writers (tabular/CSV rating reports)
    pipeline.py         # thin orchestration: process_* drivers over RatingsDB
    cli.py              # `coco-rate` entry point (main); __main__.py delegates here
    players.py          # PlayerDB   (name <-> CoCo id)
    tournaments.py      # TournamentDB (chronological driver)
    paths.py            # anchors data/ and results/ to the project root
web/                    # Django site (two apps; see "Web site" below)
    manage.py
    cocoweb/            # Django project (settings, urls, wsgi)
    players/            # player identity: search, /manage CRUD, CSV import
    ratings/            # computed-ratings projection: build_db + Tournament/CurrentRating/…
    static/             # players app css/js/logo
scripts/                # standalone / experimental scripts (not core)
tests/                  # engine unittest suite, incl. golden-master test
data/  results/  docs/  testdata/   # kept at repo root
# data/players-list.csv — org player-identity seed (Name,Number) for the players app
```

## Commands

Environment is managed by **uv** (this is an Arch/PEP-668 externally-managed
host, so a project venv is required — do not `pip install` into system Python).

Shortcuts: `make test` runs both test suites; `make run` builds the DB and
starts the dev server. The full commands:

```bash
# One-time / after dependency or metadata changes: create .venv and install editable
uv sync

# Run the tests (must run through the venv so `coco_ratings` is importable)
uv run python -m unittest              # whole suite
uv run python -m unittest tests.test_golden   # just the golden-master test

# Regenerate the golden file after an INTENTIONAL behaviour change
UPDATE_GOLDEN=1 uv run python -m unittest tests.test_golden

# Lint (config in pyproject.toml [tool.ruff])
uv run ruff check .

# Web site (Django, optional 'web' extra)
uv sync --extra web                    # install Django (+ gunicorn)
uv run python web/manage.py migrate    # apply schema
uv run python web/manage.py import_csv --current data/players-list.csv  # seed players
uv run python web/manage.py build_db   # rebuild the ratings projection from results/
uv run python web/manage.py test players ratings   # both apps' suites
uv run python web/manage.py runserver  # browse locally (or: make run)

# Rate the full history and write the current combined ratings list to a file
uv run coco-rate <output.txt>          # console script -> cli.main
# equivalently: uv run python -m coco_ratings <output.txt>

# Launch the Tk GUI (no argument)
uv run coco-rate
```

**Do not run `rating.py` directly.** Its `__main__` is intentionally stubbed to
print a reminder and exit — `pipeline.py` is the real entry point because a
single tournament can only be rated in the context of everything before it.

**`tests/test_golden.py`** is a characterization test: it replays the entire
history and diffs an exhaustive snapshot against `tests/golden_all_ratings.txt`.
Any refactor that changes the numbers fails it. The values are only reproducible
on a matching CPython/platform (generated on CPython 3.14) — regenerate if you
change interpreter.

## Architecture

The core insight: a player's new rating depends on their opponents' *current*
ratings, so ratings are always recomputed by replaying the entire tournament
history in chronological order. There is no persisted rating state between runs.

The single-tournament code is split into layers with an acyclic dependency
graph (`types` ← `io` ← `rating` ← `gui`):

**`types.py`** — the pure data model: `Player`, `Section`, `GameResult`, and the
`MAX_DEVIATION` / `UNRATED_INIT_RATING` constants. No dependency on `io` or
`rating`, which is what keeps the graph acyclic.

**`io.py`** — the file-format layer (imports `types`). Pluggable reader/writer
classes selected by file extension:

- **Results readers** (`ResultCSVReader` for `.csv`/`.tsv`, `TouReader` for
  AUPAIR `.tou`) parse game-by-game results into `Player` objects grouped into
  `Section`s. `.csv` results carry no metadata, so name/date must be passed in;
  `.tou` files embed them.
- **Ratings-file readers** (`CSVRatingsFileReader`, `RTFileReader`) load the
  pre-tournament rating list into a dict of `Player`s.
- **Writers** (`TabularResultWriter` → `.txt`, `CSVResultWriter` → `.csv`,
  `TouResultWriter` → `.tou`, `RTFileWriter` → `.RT`) emit results/ratings.
  Writers/readers only duck-type `Tournament`/`PlayerList`, so `io` needs
  nothing from `rating`.

**`rating.py`** — the engine (imports `types` + `io`). Everything funnels
through the `Tournament` class, which wires a `PlayerList` (loaded via `io`
readers) to the parsed result sections and drives rating. Also holds the
headless CLI (`run_cli`); its `__main__` is a stub that refuses to run.

**`gui.py` / `gui_app.py`** — the Tk layer. `gui.py` holds the widgets and base
`App`/`SimulationApp`; `gui_app.py` holds the subclasses that wire them to the
pipeline. **Nothing headless imports these** — `gui_app` is loaded lazily by
`cli.run_gui` and the simulation script, and `pipeline` does *not* import `gui`.
This keeps Tk (and its C libs) out of the web/`build_db` path, which matters in
the slim server container.

`RatingsCalculator` holds the actual math. Two-phase per section: iteratively
solve for unrated players' seed ratings until convergence
(`calc_initial_ratings`), then rate everyone (`calc_new_rating_for_player`).
Key tunables: `beta` (rating points per point of expected spread, default 5) and
`tau`. `_player_multiplier` damps rating changes for established/high-rated
players. Rating deviation grows with inactivity (`adjust_initial_deviation`).

**`ratingsdb.py`** — `RatingsDB`, the carry-forward engine. It rates one
tournament at a time; `adjust_tournament` overwrites each returning player's
`init_rating`/`deviation`/`career_games` with their carried-forward values from
prior tournaments before rating. `beta` (the rating-system tuning parameter,
which simulations vary) is a constructor arg, threaded in from the caller. Also
holds the `PlayerRecord`/`PlayerReport` snapshot records and `CSVRatingsFileWriter`.

**`reports.py`** — pure output writers. Given an already-computed `RatingsDB`
(and optionally the latest tournament), they render the combined ratings list
(`complete-ratings-list.csv`) and the per-tournament report. They know nothing
about the replay, so `pipeline` imports them, not vice versa.

**`pipeline.py`** — thin orchestration over `RatingsDB`. `process_old_results`
walks every tournament in date order (via `TournamentDB`) to build the current
`RatingsDB`; `write_current_ratings` / `write_sim_report` drive that replay and
hand off to `reports`. Deliberately imports no GUI, so it's safe to import in
headless contexts (the web `build_db` command).

**`cli.py`** — the `coco-rate` entry point. `main()` dispatches: an argument
writes the combined ratings list to that file; no argument launches the GUI.
`__main__.py` just delegates here so `python -m coco_ratings` works too.

**`players.py` / `tournaments.py`** — thin CSV-backed lookup tables in `data/`.
`PlayerDB` (`data/players.csv`) maps player name ↔ CoCo id. `TournamentDB`
(`data/tournaments.csv`) is the chronological list that drives the replay; its
`Filename` column is the prefix used to locate result/rating files.

**`paths.py`** — resolves `data/` and `results/` relative to the project root
(via `__file__`), so the pipeline works from any working directory. If you move
the package depth, fix `PROJECT_ROOT = parents[2]` here.

### Web site (`web/`) — two apps, one identity

One Django site (deployed as the `cocodb` Dokku app) with two apps sharing a
single player identity. `../cocodb` was merged in here — its history is preserved
in this repo's log.

**`players`** — the canonical player **identity** (from cocodb): `Player`
(`player_number` unique, `name`). This is **persistent data**, managed via the
auth-gated `/manage/` CRUD and `import_csv`, and is the FK target for the
computed ratings. There are no stored ratings here — `Player.current_rating` is a
property that returns the player's computed rating (`ratings.CurrentRating`).
Public fuzzy **search** at `/` (Postgres pg_trgm, `icontains` fallback on SQLite).
Seed the identity table with: `import_csv --current data/players-list.csv` (the
`Rating` column, if present, is ignored).

**`ratings`** — the computed-ratings projection. **Key principle: this projection
is a rebuildable view of `results/`, never a source of truth.** `Tournament`,
`CurrentRating` (1:1) and `TournamentResult` (per player-tournament, incl. record
+ spread) all FK to `players.Player`.
- `build_db` runs `process_old_results`, then in **one transaction** truncates +
  rebuilds the projections, matching each computed player to a `players.Player`
  **by name**. It creates no identity — computed names with no `Player` record
  (e.g. "Bye", "Test Player") are **skipped and flagged** in the output. Idempotent
  and safe to run on every deploy.
- The computed reverse accessor on `players.Player` is `computed_rating`; the
  `Player.current_rating` property wraps it as the single rating shown everywhere.
- `web/ratings/tests.py` is the DB-layer golden check (DB == engine): it seeds a
  `players.Player` per engine player, builds, and asserts every row matches.

**URLs**: player search at `/`, `/manage/…`, `/player/<pk>/` (player page: the
computed rating + tournament history); computed ratings namespaced under
`/ratings/` (`ratings:` names); admin at `/django-admin/`.

Django is an optional `web` extra (`uv sync --extra web`); the `coco_ratings`
engine stays dependency-free. Prod uses Postgres via `DATABASE_URL`; SQLite
locally. The hashed/manifest static backend is used only in prod (collectstatic
runs in the Docker build); dev/tests use plain storage. Run `manage.py test
players ratings` for both apps (bare `manage.py test` misses `web/` apps).

**`results/`** — the historical corpus. Each tournament is a pair of files:
`<prefix>-results.{csv,tsv}` and `<prefix>-ratings.{csv,tsv}`. The `<prefix>`
must match the `Filename` column in `data/tournaments.csv`. Adding a tournament
means dropping in these two files and adding a row there.

## Deployment (Dokku + Ansible)

Deploys to a Dokku server; Ansible config lives in the sibling `../vps` repo
(app name **`cocodb`**, `cocodb.cocoscrabble.org`). The DB is Postgres in prod
(injected as `DATABASE_URL` by `dokku-postgres`) and SQLite locally — settings
switch on `DATABASE_URL`. `results/` ships inside the image, so the container
always has the source of truth.

- **`Dockerfile`** — uv build (`uv sync --extra web`), runs `collectstatic`
  (WhiteNoise serves it), gunicorn as the web process.
- **`Procfile`** — `release: migrate && build_db` (rebuilds the ratings
  projection from `results/` on every deploy, atomically/idempotently),
  `web: gunicorn`. Player identity is **persistent** (managed via `/manage`), so
  on the *first* deploy seed it once:
  `dokku run cocodb python web/manage.py import_csv --current data/players-list.csv`,
  then re-run `build_db` (or redeploy) so it matches.
- **Env vars** are set by `../vps` `configure-app.yml`: `SECRET_KEY`,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG` (settings read these
  unprefixed names). `cocodb_builder: dockerfile` and `cocodb_ports` are in the
  vps `production.yml`.
- **CI/CD** (`.github/workflows/ci.yml`): tests on every push/PR; on push to
  `main`, deploys to Dokku via `dokku/github-action`. One-time setup: add the
  deploy key as GH secret `DOKKU_SSH_PRIVATE_KEY` and its public half to Dokku
  (`dokku ssh-keys:add github <pubkey>`).
- **First-time provisioning** (from `../vps`, playbooks are idempotent):
  `new-app.yml -e app_name=cocodb` (app + Postgres + domain + LE),
  `configure-app.yml -e app_name=cocodb` (env + builder + ports),
  `sync-domains.yml -e app_name=cocodb` (extra hosts).

## File formats

- **Results CSV** columns: `Submitted On, Round, Winner, Winners Score, Opponent, Opponents Score` (header row is skipped).
- **Ratings CSV** columns: `Name, Rating, Email` (rating `0` ⇒ unrated).
- `.tou` and `.RT` are legacy AUPAIR formats supported for interop; readers/writers
  live in `io.py`. Extension determines the parser, so name files correctly.
- Player identity is by exact name string across all files — name mismatches
  create phantom unrated players, so consistency matters.

## Notes

- Byes/forfeits are filtered by name (see the `byes` set in `Tournament.output_ratfile`) and skipped in rating math.
- `output_active_ratfile` reads a `removed_people.txt` (deceased/removed players) that is not checked in.
- The repo root accumulates scratch output files (`*.csv`, `*.txt`, logs) from runs; these are working artifacts, not source.
