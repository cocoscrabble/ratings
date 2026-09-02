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
    core/               # dependency-free core: imports nothing but stdlib
        types.py        # data model: Player, Section, GameResult, constants
        calculator.py   # RatingsCalculator — the rating math
    types.py            # re-export shim for core/types.py (stable import path)
    identity.py         # canonical_player_number() -- shared with Baxter
    logging_setup.py    # configure_file_logging(); entry points only, never a library
    io.py               # file readers/writers (CSV/TSV, .tou, .RT) + parsing
    rating.py           # Tournament, PlayerList, CLI; re-exports RatingsCalculator
    gui.py              # Tk widgets + base App/SimulationApp (imports nothing heavy)
    gui_app.py          # GUI apps wiring Tk to the pipeline (keeps pipeline Tk-free)
    ratingsdb.py        # RatingsDB (carry-forward replay), PlayerRecord/PlayerReport
    reports.py          # pure output writers (tabular/CSV rating reports)
    pipeline.py         # thin orchestration: process_* drivers over RatingsDB
    cli.py              # `coco-rate` entry point (main); __main__.py delegates here
    players.py          # PlayerDB   (name <-> CoCo id)
    tournaments.py      # TournamentDB (chronological driver)
    paths.py            # anchors data/ and results/ to the project root
web/                    # Django site (three apps; see "Web site" below)
    manage.py
    cocoweb/            # Django project (settings, urls, wsgi)
    accounts/           # site accounts: custom User model + the staff gate
    players/            # player identity: search, /manage CRUD, CSV import
    ratings/            # computed-ratings projection: build_db + Tournament/CurrentRating/…
    static/             # players app css/js/logo
scripts/                # standalone / experimental scripts (not core)
    deploy.sh           # manual deploy (see "Deployment" below)
    rating_history.py   # git archaeology: which commits moved ratings
tests/                  # engine unittest suite, incl. golden-master test
data/  results/  docs/  plans/  testdata/   # kept at repo root
# plans/ — design/implementation notes for larger work (see plans/README.md);
#   docs/ is static human reference material. Put new plans in plans/.
# data/players.csv — the single player-identity list (Name,Number): the
#   engine's name<->CoCo-id map AND the players app's seed
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
uv run python web/manage.py import_csv --current data/players.csv  # seed players
uv run python web/manage.py build_db   # rebuild the ratings projection from results/
uv run python web/manage.py test accounts players ratings  # all three apps
uv run python web/manage.py runserver  # browse locally (or: make run)

# Rate the full history. The named file gets the LATEST tournament's per-player
# results; the combined list always goes to ./complete-ratings-list.csv
uv run coco-rate <output.csv>          # console script -> cli.main
# equivalently: uv run python -m coco_ratings <output.csv>

# Launch the Tk GUI (no argument)
uv run coco-rate
```

**Do not run `rating.py` directly.** Its `__main__` is intentionally stubbed to
print a reminder and exit — `pipeline.py` is the real entry point because a
single tournament can only be rated in the context of everything before it.

**`tests/test_golden.py`** is a characterization test: it replays a **pinned
prefix** of the history and diffs an exhaustive snapshot against
`tests/golden_all_ratings.txt`. Any refactor that changes the numbers fails it.

The input is fixed to tournaments dated on or before `GOLDEN_CUTOFF`
(`2025-12-31`, 108 tournaments), via `process_old_results(until=…)`, so **adding
a tournament does not touch this test** — it only measures the math. Regenerate
the golden file for an *intentional* math change, when moving the cutoff, or
when back-filling a tournament dated before it. The values are only reproducible
on a matching CPython/platform (generated on CPython 3.14) — regenerate if you
change interpreter. For that reason it is a **local-only** check: CI sets
`SKIP_GOLDEN=1`, which skips the whole test case.

## Architecture

The core insight: a player's new rating depends on their opponents' *current*
ratings, so ratings are always recomputed by replaying the entire tournament
history in chronological order. There is no persisted rating state between runs.

The single-tournament code is split into layers with an acyclic dependency
graph (`core` ← `io` ← `rating` ← `gui`):

**`core/`** — the dependency-free heart: the data model (`core/types.py`:
`Player`, `Section`, `GameResult`, the `MAX_DEVIATION` /
`UNRATED_INIT_RATING` constants) and the math (`core/calculator.py`:
`RatingsCalculator`). It imports nothing but the standard library — not `io`,
and **no logging configuration** — which is what keeps the graph acyclic *and*
what lets Baxter (`../baxter`, the tournament manager) import the same rating
math for live in-tournament projections rather than reimplementing it.

That contract is enforced mechanically by `tests/test_core_isolation.py`; see
`plans/baxter-integration.md`. `coco_ratings/types.py` remains as a re-export
shim, so `io`, `ratingsdb`, `gui` and the tests keep their existing import path.

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

**`rating.py`** — the io-dependent glue (imports `core` + `io`). Everything
funnels through the `Tournament` class, which wires a `PlayerList` (loaded via
`io` readers) to the parsed result sections and drives rating. Also holds the
headless CLI (`run_cli`); its `__main__` is a stub that refuses to run. It
re-exports `RatingsCalculator` from `core`, which is where the math now lives —
`from coco_ratings.rating import RatingsCalculator` still works.

**`identity.py`** — `canonical_player_number()`: the single definition of
whether `233` and `0233` are the same person. It lives in the shipped package
rather than in `web/players/models.py` (which now imports it) because **Baxter
imports it too** — the two projects key players by this number and exchange
rosters and results by it, so two implementations would eventually disagree
about identity and split one person in two on both sides at once. Non-numeric
keys pass through untouched, which is what lets Baxter's `T-7` placeholders and
`BYE` survive canonicalization.

**`logging_setup.py`** — `configure_file_logging()`, called by `cli.main()`.
`rating.py` used to call `logging.basicConfig` *at import*, which reconfigured
the root logger of anything importing it, wrote a DEBUG file into the working
directory (this is where the multi-GB `coco_ratings.log` came from), and cost
~90% of the test suite's runtime. Entry points configure logging; libraries
never do.

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
`PlayerDB` (`data/players.csv`) maps player name ↔ CoCo id, and is the *same*
file the players app is seeded from — identity lives in one place. Numbers are
written bare (`233`) in `data/players.csv` but **either form is accepted**:
readers normalize, so a hand-pasted `0233` is the same player, not a second one.

In the site's DB the stored key is the **zero-padded** form (`0233`) — see
`canonical_player_number`, which every write funnels through, including
`Player.save()`. Which spelling is canonical is a storage detail; what matters
is that there is exactly one, since `player_number` is a *string* key and two
spellings would split one person into two identities. **URLs stay bare**
(`/player/233/…`), so links predating the padding remain canonical; lookups
normalize, so `/player/0233/` resolves to the same player.
`Player.padded_number` survives as an alias of `player_number` because
templates and the search JSON refer to it.
`TournamentDB`
(`data/tournaments.csv`) is the chronological list that drives the replay; its
`Filename` column is the prefix used to locate result/rating files. Columns are
`FancyName, Division, City, Name, Tournament, Filename, Date, Order` — `Date` is
`yyyy-mm-dd` and is the only source of the date (the old redundant `Month`,
`Day`, `Year` columns are gone).

Entries sort by `(date, sort_order, filename)`. **`Order` exists because the
replay order is part of the result**: ratings carry forward, so two tournaments
on the same day that share players give different ratings depending on which is
rated first, and the date cannot express that. Blank `Order` is 0, so rows that
don't need it keep sorting by filename exactly as before. `ratings.Tournament`
mirrors the field so the site's chronology matches the rating order; a player
page ordered any other way would show one row's `new_rating` not matching the
next row's `old_rating`.

**`paths.py`** — resolves `data/` and `results/` relative to the project root
(via `__file__`), so the pipeline works from any working directory. If you move
the package depth, fix `PROJECT_ROOT = parents[2]` here.

### Web site (`web/`) — three apps, one identity

One Django site (deployed as the `cocodb` Dokku app) with three apps sharing a
single player identity. `../cocodb` was merged in here — its history is preserved
in this repo's log.

**`accounts`** — who can log in. `AUTH_USER_MODEL = "accounts.User"`, an
`AbstractUser` subclass, so later changes (profile fields, or moving the login
identity to email) are ordinary migrations rather than a swap of the user model
on a populated database. It carries a nullable `player` OneToOne to
`players.Player`, which is the hook for the planned **regular users** — people
with an account who are linked to their own player row.

That link is *only* a link and confers no rights over the `Player` row.
`build_db` matches computed players to `players.Player` **by name**, so a
self-service rename would silently orphan that player's entire tournament
history; name and number stay staff-owned. Anything a user may edit about
themselves belongs on the user, not on the player.

Two kinds of account exist:

- **Staff** (`is_staff`) — administrators. `/manage` is gated on this flag by
  `accounts.decorators.staff_required`, **not** on `login_required`. The
  distinction is load-bearing: `/manage` rewrites player identity and bulk-imports
  the player list, so the moment a non-staff account exists, `login_required`
  would hand it those powers. Anonymous visitors are redirected to login; a
  logged-in non-staff user gets a 403 (redirecting would loop). `/manage/login/`
  uses `StaffAuthenticationForm`, which refuses a correct non-staff password
  rather than granting a session that 403s everywhere.
- **Regular users** — not built yet. Nothing blocks them; the gate and the link
  are in place.

Accounts are managed in `/django-admin/` (superuser-only): creating staff,
resetting passwords, and linking an account to a player. There is no mail service
configured, so there is **no self-service password reset** — a superuser resets
them. Adding one later means setting `EMAIL_*` in settings and wiring Django's
`PasswordReset*` views.

`accounts/tests.py` is the access-control matrix (anonymous / non-staff / staff /
inactive, over every `/manage` URL). `test_all_manage_urls_are_covered` fails if a
new `manage/` URL is added without being gated, so a new admin view cannot
quietly ship open.

**`players`** — the canonical player **identity** (from cocodb): `Player`
(`player_number` unique, `name`). This is **persistent data**, managed via the
auth-gated `/manage/` CRUD and `import_csv`, and is the FK target for the
computed ratings. There are no stored ratings here — `Player.current_rating` is a
property that returns the player's computed rating (`ratings.CurrentRating`).
Public fuzzy **search** at `/` (Postgres pg_trgm, `icontains` fallback on SQLite).

`PlayerDetails` (1:1, `player.details`) holds optional contact/admin data —
country, state, city, email, phone, payout preference, comments; every field
blank-able, so most players have no row at all and nothing may assume one
exists. It is kept out of `Player` because the lifecycles differ: identity is
re-seeded from `data/players.csv` on every deploy, whereas this is hand-entered
and reproduced by no file, so it must never be rewritten by a deploy or a
rebuild. It is also the site's first **private** data — player pages and the
search JSON are public, so nothing here may be rendered there;
`PlayerDetailsPrivacyTest` fails if it ever is. Edited through `/django-admin/`
as an inline on the player (superuser-only); deliberately *not* in `/manage`,
which is staff-wide.
Seed the identity table with: `import_csv --current data/players.csv` — the same
file the engine reads, so a new player is added in exactly one place (a `Rating`
column, if present, is ignored).

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

**URLs** (no DB pks in public URLs — use each model's `get_absolute_url`):
player search at `/`, `/manage/…`, and the player page at
`/player/<number>/<name-slug>/` (looked up by the unique `player_number`; the
slug is decorative and a stale/absent slug 301-redirects to canonical). Computed
ratings under `/ratings/` (`ratings:` names); tournament pages at
`/ratings/tournament/<slug>/` where the slug is the tournament `filename` (already
a unique, hyphenated identifier). Admin at `/django-admin/`; login at
`/manage/login/`, logout is POST-only (Django 5+ dropped GET logout, so the
templates use a form, not a link).

Django is an optional `web` extra (`uv sync --extra web`); the `coco_ratings`
engine stays dependency-free. Prod uses Postgres via `DATABASE_URL`; SQLite
locally. The hashed/manifest static backend is used only in prod (collectstatic
runs in the Docker build); dev/tests use plain storage. Run `manage.py test
accounts players ratings` for all three apps (bare `manage.py test` misses `web/`
apps). Outside DEBUG, settings refuse to start on the dev `SECRET_KEY` fallback
(it signs session cookies, so it would make staff sessions forgeable) and turn on
`SECURE_SSL_REDIRECT` / secure cookies / HSTS; the Dockerfile's `collectstatic`
therefore passes a throwaway key, since it serves no requests.

**`results/`** — the historical corpus. Each tournament has a
`<prefix>-results.{csv,tsv}` and an **optional** `<prefix>-ratings.{csv,tsv}`.
The `<prefix>` must match the `Filename` column in `data/tournaments.csv`.
Adding a tournament means dropping in the results file (plus a ratings file if
needed) and adding a row there.

The ratings file is **largely redundant**: `RatingsDB.adjust_tournament`
overwrites every returning player's seed from the accumulated carry-forward
ratings, so the file only supplies a starting rating for players making their
*first* appearance in the whole history. A missing ratings file is handled
gracefully (`pipeline.process_old_results` passes `ratings_file=None`) — it is a
no-op for any tournament whose players have all played before, and otherwise
just reseeds genuine first-timers from their own results. A minimal ratings file
listing *only* the new players is therefore sufficient. See
`tests/test_missing_ratings.py`.

## Deployment (Dokku + Ansible)

Deploys to a Dokku server; Ansible config lives in the sibling `../vps` repo
(app name **`cocodb`**, `cocodb.cocoscrabble.org`). The DB is Postgres in prod
(injected as `DATABASE_URL` by `dokku-postgres`) and SQLite locally — settings
switch on `DATABASE_URL`. `results/` ships inside the image, so the container
always has the source of truth.

- **`Dockerfile`** — uv build (`uv sync --extra web`), runs `collectstatic`
  (WhiteNoise serves it), gunicorn as the web process.
- **`Procfile`** — `release: migrate && import_csv && build_db`, `web: gunicorn`.
  The release phase seeds identity from `data/players.csv` and then rebuilds the
  ratings projection from `results/`, on every deploy. Both steps are idempotent,
  so adding a player is just a commit: no manual `dokku run` needed. Identity
  stays **persistent** — `import_csv` without `--update` only ever *adds* rows,
  so it never disturbs edits made through `/manage`. A row it rejects raises
  `CommandError`, which fails the release and aborts the deploy, leaving the
  running version up; `players.SeedFileImportTest` guards the file in CI.
- **The custom user model swap is done** (August 2026). It needed a one-time
  manual database step, since `AUTH_USER_MODEL` cannot be swapped on a database
  already migrated against `auth.User`. Nothing is outstanding, and a fresh
  database needs no special handling; `plans/auth-migration.md` keeps the record
  of why `accounts` exists and how the live database was moved.
- **Env vars** are set by `../vps` `configure-app.yml`: `SECRET_KEY`,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DEBUG` (settings read these
  unprefixed names). `cocodb_builder: dockerfile` and `cocodb_ports` are in the
  vps `production.yml`.

  `ROSTER_API_TOKEN` is the shared static token for `GET /api/roster/`, the
  roster Baxter pulls. It is set by Ansible as well, via `cocodb_extra_config` /
  `baxter_extra_config` in `production.yml` — one value with two roles (we check
  it, Baxter presents it), so the two must rotate together or the pull starts
  401ing. The value lives in the vault-encrypted `secrets.yml`. Config is set
  with `--no-restart`, so a change takes effect on the next deploy unless you
  follow with `dokku ps:restart`. Leaving it unset disables the endpoint rather
  than opening it, so forgetting is safe; the download at
  `/manage/roster/download/` works either way.
- **CI/CD** (`.github/workflows/ci.yml`): tests on every push/PR; on push to
  `main`, deploys to Dokku via `dokku/github-action`. One-time setup: add the
  deploy key as GH secret `DOKKU_SSH_PRIVATE_KEY` and its public half to Dokku
  (`dokku ssh-keys:add github <pubkey>`).
- **Manual deploy** (`scripts/deploy.sh`, `make deploy`) — the fallback when
  Actions is unavailable. Same steps as the CI deploy job, run locally: the test
  suites, then `git push <dokku remote> HEAD:main`, which triggers the Procfile
  release phase on the server. `--skip-tests`, `--force`, and `--rebuild` (no
  push; `ps:rebuild` to re-run release + `build_db` against deployed code).
  Needs SSH access as `dokku@$DOKKU_HOST`; host/app/remote names are env-var
  overridable. Note it deploys the *committed* HEAD and bypasses GitHub, so
  `origin` must be pushed separately.
- **First-time provisioning** (from `../vps`, playbooks are idempotent):
  `new-app.yml -e app_name=cocodb` (app + Postgres + domain + LE),
  `configure-app.yml -e app_name=cocodb` (env + builder + ports),
  `sync-domains.yml -e app_name=cocodb` (extra hosts).

## File formats

- **Results CSV** columns: `Submitted On, Round, Winner, Winners Score, Opponent, Opponents Score`.
  `Winner Number, Opponent Number` may be **appended** — the number-bearing form
  Baxter produces. Readers dispatch on the header (`io.find_number_columns`),
  matching normalized column *names*, and expose which form they read as
  `keyed_by`. The columns are appended rather than interleaved because the six
  legacy fields are unpacked positionally; a column inserted among them shifts
  every later field. Half a pair is an error, not a per-row decision.
- **Ratings CSV** columns: `Name, Rating, Email` (rating `0` ⇒ unrated), with an
  optional appended `Number`, for the same positional reason. Optional
  per tournament (see `results/` above); when present it only seeds first-timers.
- **`data/tournaments.csv`** columns: `FancyName, Division, City, Name,
  Tournament, Filename, Date, Order` — `Date` is `yyyy-mm-dd`; `Order` breaks
  ties between same-day tournaments (see `TournamentDB` above).
- `.tou` and `.RT` are legacy AUPAIR formats supported for interop; readers/writers
  live in `io.py`. Extension determines the parser, so name files correctly.
- Player identity is the **number when a file carries one, the name otherwise**
  (`Player.key`). In the name-keyed corpus that is the exact name string, so
  name mismatches still create phantom unrated players and consistency still
  matters. The two forms meet in `PlayerList.find_or_add_player` and
  `RatingsDB.key_for`: someone met with a number who is already on file under
  their name is the *same person*, so their record and history migrate onto the
  number and a name→number alias is remembered. Without both halves, the first
  number-keyed tournament resets a career to unrated and the next name-keyed one
  splits it again. See `plans/baxter-integration.md` phase 2.

## Rating archaeology (`scripts/rating_history.py`)

Answers "did this commit change anyone's rating?" — which cannot be read off a
diff, because ratings keep no persisted state and are recomputed by replaying
the whole corpus. The tool walks every commit that touched a `.py` file,
materialises that commit's tree *and* its parent's with `git archive` (so a
dirty checkout is fine), replays both, and diffs the ratings lists.

`plans/rating-history.md` is the committed run over the full history. Of 200
commits touching `.py`, **four** ever moved a rating: bye handling
(`da077423a3`), forfeit handling (`906445ab82`), applying the inactivity
deviation adjustment in the carry-forward (`546051b407`), and the switch to
real tournament dates (`c5aa5ff05a`).

Two traps, both already handled — do not "simplify" them away:

- **The editable install.** `.venv/…/__editable__.coco_ratings-0.1.0.pth` puts
  the live `src/` on `sys.path`, so `import coco_ratings` succeeds for *any*
  tree, including every commit predating the src layout. Those commits then get
  evaluated as HEAD and the tool reports that nothing ever changed. The replay
  subprocess therefore runs with `-S -E`, and the driver rejects a module whose
  `__file__` is outside the extracted tree.
- **The tournament list used to be code.** Until `c5aa5ff05a` (2025-11-16) it
  lived in `all_rating.py`, so adding a tournament was a `.py` change. Those
  commits move ratings without touching the maths, so the `.py` diff is
  classified and they are reported in a separate section.

Entry points are probed newest-first (`coco_ratings.pipeline` → `pipeline` →
`all_rating` → `rating`), since the module moved four times. Commits with no
replay at all — 2021, which predates `process_old_results`, and the merged-in
`cocodb` Django history — are listed as not replayable rather than skipped.
`--cache` makes re-rendering free; `--commit SHA` reports one commit in full.

## Notes

- Byes/forfeits are filtered by name (see the `byes` set in `Tournament.output_ratfile`) and skipped in rating math.
- `output_active_ratfile` reads a `removed_people.txt` (deceased/removed players) that is not checked in.
- The repo root accumulates scratch output files (`*.csv`, `*.txt`, logs) from runs; these are working artifacts, not source.
