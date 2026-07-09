# Merge plan: fold `../cocodb` into this project

Goal: one Django site (deployed as the `cocodb` Dokku app, `playerdb.cocoscrabble.org`)
combining the **player database** (identity, search, `/manage` CRUD, published
ratings, CSV import — from `../cocodb`) with the **tournament-computed ratings**
(engine + `web/ratings`, this project).

## Decisions (locked)

1. **History**: preserve cocodb's commits via a subtree/`--allow-unrelated-histories` merge.
2. **Identity**: one canonical `players.Player`; computed tables FK to it; drop `ratings.Player`.
3. **Rating sources**: keep **both** published `players.Rating` (manual) and computed
   `ratings.CurrentRating`/`TournamentResult`; show both on the player page.
4. **Homepage**: player search at `/`; ratings list at `/ratings/`, tournaments at `/tournaments/`.
5. **Unknown players** (names in `results/` not in the player table): **skip and flag**
   (report them); do **not** auto-create. A real "add new players" flow comes later.
6. Engine stays file-based (`data/`+`results/`); `build_db` links computed ratings to
   `players.Player` **by name** at rebuild time.
7. One project (`web/cocoweb`), two apps (`players`, `ratings`); one Dockerfile/Procfile;
   Python 3.14; psycopg3; keep the Ansible env-var convention.

## Phase A — bring cocodb in, both apps working side by side ✅

- [x] Subtree-merge cocodb under `cocodb-import/` (history preserved).
- [x] Relocate: `players/` → `web/players/`, `static/` → `web/static/`, keep the published
      CSV as `data/published-ratings.csv`; drop cocodb's project/manage/Docker/Procfile/etc.
- [x] Fold cocodb settings into `web/cocoweb/settings.py` (add `players` app, LOGIN_URL,
      STATICFILES_DIRS, password validators). Kept our env-var convention + dj-database-url.
- [x] Deps: reused our web extra (psycopg3, dj-database-url — dropped django-environ /
      psycopg2). pg_trgm migration ships as-is (no-op on SQLite).
- [x] URLs: `players.urls` at `/`, `ratings.urls` namespaced at `/ratings/` (ratings
      templates/tests now use `ratings:` names). admin at `/django-admin/`.
- [x] Green: migrations apply; engine 5 + players 6 + ratings 11 tests; ruff + pyright clean.
      Live-checked routes (/, /ratings/, /manage/login/, /search/) all 200;
      `import_csv --current data/published-ratings.csv` seeds 222 players.

## Phase B — unify Player identity ✅

- [x] Repoint `ratings.CurrentRating`/`TournamentResult` FKs to `players.Player` (string ref;
      computed OneToOne is `computed_rating` to avoid clashing with the published
      `current_rating` property). Dropped `ratings.Player` (migration 0002).
- [x] Rewrote `build_db`: matches `players.Player` by name, skips + flags unmatched (prints a
      report, creates nothing). On the real data it skips exactly "Bye" and "Test Player"
      (222 players / 1329 results). DB-golden test green (seeds a Player per engine player).
- [x] Merged the player page into the players app: published rating + computed rating +
      tournament history; ratings/tournament tables link back to it. Removed ratings'
      player_detail view/url/template.
- [x] Fixed static storage: manifest (hashed) backend only in prod; plain in dev/tests so
      `{% static %}` works without collectstatic. Green: engine 5 + players 6 + ratings 10;
      ruff + pyright clean.

## Phase C — deploy as one app ✅

- [x] Single `Dockerfile` + `Procfile` already target `cocoweb.wsgi` + `migrate && build_db`
      (from phase 3); cocodb's deploy files were dropped in the relocation. `../vps` cocodb
      config (dockerfile builder, ports, extra_hosts, secret) already in place.
- [x] Verified in a container: build + migrate + import players + build_db + gunicorn; `/`,
      `/search/`, `/ratings/`, `/manage/login/`, static, and the unified `/player/<pk>/`
      (published + computed + history) all 200.
- [x] Updated `Makefile` (run seeds players then rebuilds), `.github/workflows` (test both
      apps), and `CLAUDE.md`. Player identity is persistent; first deploy seeds it once via
      `import_csv`, documented in CLAUDE.md.

## Done. Follow-ups (separate work)

- An "add new players" flow so skipped names (currently "Bye"/"Test Player" only) can be
  onboarded, per the deferred decision.
- Consider whether computed ratings should feed the published `Rating` list, or stay separate.

## Safety net

Golden test (engine) + DB-golden test (`build_db` == engine) stay green through Phase B
(the riskiest part); cocodb's tests guard search/CRUD. Every phase ends green.
