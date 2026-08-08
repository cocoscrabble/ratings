# CoCo ratings

Rating software for CoCo tournaments. The published ratings live at
<https://cocodb.cocoscrabble.org>.

Ratings use the Norwegian system, a spread-based, Glicko-style rating; see
`docs/norwegian-rating.pdf`. Sample input files are under `testdata/`, and the
historical results that the published ratings are computed from are in
`results/`.

### Adding a tournament

Adding a tournament is entirely a matter of editing CSV files and pushing to
`main`. Everything downstream (tests, deploy, rebuilding the site's database)
happens automatically. You do not need to run anything on the server.

**1. Add the results file** as `results/<prefix>-results.csv`, where `<prefix>`
is a short hyphenated identifier for the tournament (e.g. `wordcup-2026-eb`).

NOTE: The results file is typically exported from the tournament management software;
you should not have to create it by hand.

**2. Add a row to `data/tournaments.csv`**, whose `Filename` column must be
exactly the `<prefix>` you used above — that is how the results file is found.
`Date` is `yyyy-mm-dd`:

```
FancyName,Division,City,Name,Tournament,Filename,Date,Order
Word Cup,EB,Williamsburg,,,wordcup-2026-eb,2026-07-31,
```

Leave `Order` blank unless **two tournaments share a date**. Ratings are carried
forward from one tournament to the next, so if a player appears in both, the
order they are rated in changes the answer — and a date alone cannot say which
came first. When that happens, number the events of that day `1`, `2`, `3` …:

```
Word Cup,D1,Williamsburg,,,wordcup-2026-d1,2026-08-05,1
Word Cup,D2,Williamsburg,,,wordcup-2026-d2,2026-08-05,2
```

Same-day rows that leave `Order` blank fall back to sorting by filename, which
is arbitrary — fine when no player played in both, wrong when someone did.

**3. Add any players who have never played before** to `data/players.csv`
(`Name,Number`), using their CoCo player number. Either `233` or `0233` works,
both are read as the same player.

NOTE: This is the one file the website's player pages are built from, so a
player missing here is rated by the engine but will not appear on the site.

**4. Optionally add a ratings file** as `results/<prefix>-ratings.csv`
(`Name,Rating`, a rating of `0` meaning unrated). This is usually unnecessary:
returning players always carry their rating forward from previous tournaments,
so the file only supplies a starting rating for players making their very first
appearance. A file listing *only* those new players is enough, and if every
player has played before you can leave it out entirely.

**5. Commit and push to `main`.**  The push runs the test suite, and on success
deploys the site and rebuilds its database from `results/`. Rebuilding is
idempotent, so re-running or re-pushing is always safe.

Then check the tournament at <https://cocodb.cocoscrabble.org/ratings/>.

If GitHub Actions is down (or the deploy otherwise does not happen), you can
deploy by hand from a checkout instead — see "Deploying by hand" below.

**Names must match exactly**, character for character, across the results file,
the ratings file and `data/players.csv`. Player identity is the name string, so
a typo or a changed spelling does not raise an error, it silently creates a
second, unrated player. If someone's rating looks wrong or they are missing from
the site, a name mismatch is the first thing to check.

Correcting a past tournament works the same way: every rating is recomputed from
the entire history on each run, so fixing a result file and pushing re-rates
everything that followed it.

### Deploying by hand

Normally you never need this: pushing to `main` deploys. But when GitHub Actions
is unavailable, `scripts/deploy.sh` does the same job from your machine — it runs
the test suites and then pushes your commit straight to the Dokku server, which
re-seeds the players and rebuilds the ratings database exactly as an automatic
deploy would.

```bash
make deploy               # or: ./scripts/deploy.sh
```

You need SSH access to the Dokku host as the `dokku` user; the script adds the
git remote itself. Useful variants:

```bash
./scripts/deploy.sh --skip-tests   # deploy now, skip the suites
./scripts/deploy.sh --rebuild      # don't deploy code, just rebuild the site's DB
./scripts/deploy.sh --force        # non-fast-forward push (e.g. after a revert)
```

Two things to watch for. Only *committed* work is deployed — the script warns
about a dirty tree, because uncommitted changes are the usual reason a deploy
looks like it did nothing. And a manual deploy does not touch GitHub, so push to
`origin` as well once Actions is back, or the repo and the live site drift apart.

### Running it locally

You only need this to inspect the ratings yourself; publishing them is just the
push described above.

The project uses [uv](https://docs.astral.sh/uv/). One-time setup:

```bash
uv sync
```

Then rate the whole history:

```bash
uv run coco-rate latest-tournament.csv
```

This replays every tournament in `data/tournaments.csv` in date order and writes
two files:

- the file you name on the command line — the **most recent tournament's**
  results
- `complete-ratings-list.csv`, in the current directory — the **combined ratings
  list**: every player's current rating, deviation and career games

The per-tournament report is also printed to the terminal. Running with no
argument opens a small Tk GUI that does the same thing from a file picker:

```bash
uv run coco-rate
```

There is no way to rate a single tournament on its own, because a player's new
rating depends on their opponents' current ratings, so the whole history is
always recomputed from scratch. There is no stored rating state between runs.

### Input formats

Files are identified by their extension, so name them correctly.

**Results** — the games played:

- `.csv` / `.tsv`: columns `Submitted On, Round, Winner, Winners Score,
  Opponent, Opponents Score`. See `testdata/loco21.csv`.
- `.tou`: the AUPAIR format. See `testdata/hoodriver.tou`.

**Ratings** — the starting ratings for a tournament:

- `.csv` / `.tsv`: columns `Name, Rating` (a rating of `0` means unrated; a
  trailing `Email` column is ignored if present). See `testdata/loco-ratings.csv`.
- `.RT`: the AUPAIR format. See `testdata/20200217_HoodRiver.RT`.

The `.RT` and `.tou` formats exist to interoperate with other programs. If you
are entering data yourself, use `.csv` — you can export it from Excel or Google
Sheets. Unlike `.tou` files, `.csv` results carry no tournament name or date, so
those come from the row in `data/tournaments.csv`.

### Development

```bash
uv run python -m unittest                          # engine tests
uv run ruff check .                                # lint

uv sync --extra web                                # install Django
uv run python web/manage.py test players ratings   # web tests
make run                                           # build the DB, serve locally
make test                                          # both test suites
```

`tests/test_golden.py` locks down the rating maths by replaying a fixed range of
tournaments and comparing an exhaustive snapshot against a checked-in file.
Adding a tournament does not affect it. If you change the maths *deliberately*,
regenerate the snapshot:

```bash
UPDATE_GOLDEN=1 uv run python -m unittest tests.test_golden
```

See `CLAUDE.md` for the architecture, the web site's design and deployment.
