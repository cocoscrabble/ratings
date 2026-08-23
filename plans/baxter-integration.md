# Baxter integration: the central side

The coco-ratings half of a two-repo piece of work. Baxter (the tournament
manager, `../baxter`) is being changed to key players by CoCo player number
instead of by name, to pull rating seeds from this project before an event, and
to show live non-binding rating projections during one using *this* project's
calculator.

The program-level design — governing principles, the interchange contract, and
the sequencing across both repos — lives in **`../baxter/plans/PLAN_COCO_PROGRAM.md`**.
Read that first; this document is only the work that happens in this repo.

References are as of `d4cd9a8`.

## What this repo has to provide

1. **A dependency-free rating core** Baxter can import without dragging in the
   file-format layer or hijacking its logging.
2. **Support for a number-keyed results format alongside the existing
   name-keyed one**, so Baxter's files stop depending on names matching across
   two systems — without disturbing the Google Form export that still produces
   name-keyed files.
3. **A roster endpoint and snapshot file**, so Baxter can pull ratings before an
   event and then run offline.

Principle worth restating because it constrains all three: **Baxter must never
need this service while a tournament is live**, and **provisional players must
never enter this database**. Baxter creates local `T-` placeholders and blocks
its own export until an admin has assigned real numbers here.

---

## Phase 1 — Extract `coco_ratings.core` — **IMPLEMENTED**

The math is already pure — `RatingsCalculator` touches nothing but `types` — but
it cannot be imported in isolation:

- `rating.py:22` calls
  `logging.basicConfig(filename="coco_ratings.log", encoding="utf-8", level=logging.DEBUG)`
  **at module import**. In this repo that is what grows `coco_ratings.log` to
  1.68 GB. In an importing application it silently reconfigures the root logger
  and starts writing a DEBUG file into whatever the working directory happens to
  be. Baxter deploys on Dokku and logs to stdout; this would quietly break that.
- `rating.py` imports six reader/writer classes from `io.py` at module level, so
  importing the calculator pulls in the whole file-format layer.

### 1a. The split

```
src/coco_ratings/
  core/
    __init__.py      # exports Player, Section, GameResult, RatingsCalculator
    types.py         # moved verbatim from ../types.py
    calculator.py    # RatingsCalculator, moved verbatim from rating.py
  types.py           # re-export shim: from coco_ratings.core.types import *
  rating.py          # imports RatingsCalculator from core; keeps Tournament,
                     # PlayerList, run_cli, and the io-dependent glue
```

- `core` imports **nothing** outside itself and the standard library. That is the
  property Baxter depends on; assert it with a test that imports
  `coco_ratings.core` in a subprocess with `io` blocked, or simply asserts
  `coco_ratings.io` is absent from `sys.modules` afterwards.
- Keep `coco_ratings.types` working as a re-export. `io.py`, `ratingsdb.py`,
  `gui.py` and the tests all import from it, and there is no reason to churn
  them.

### 1b. Logging

Delete the module-level `basicConfig`. Logging is configured by *entry points*,
not by importing a library:

- `cli.py:main()` and `gui_app.py` configure the file handler as today, so the
  CLI and GUI keep their debug log.
- `build_db` and any library consumer inherit the host's configuration.
- The per-game `logging.debug` calls in `calc_new_rating_for_player` stay — they
  are genuinely useful for rating archaeology — but they are now only expensive
  when someone has turned DEBUG on.

**Verification:** `tests/test_golden.py` must produce a **byte-identical**
golden file. The extraction is a pure move; if the golden shifts, something was
changed that should not have been. Add the import-isolation test above. Confirm
`make test` passes both suites.

### What landed

- `core/types.py` moved with `git mv` (history preserved); `core/calculator.py`
  holds `RatingsCalculator` as a **verbatim** move — the class body diffs clean
  against the original. `core/__init__.py` exports the five public names.
- `coco_ratings/types.py` is now a re-export shim, so `io`, `ratingsdb`, `gui`
  and the existing tests are untouched. `rating.py` re-exports
  `RatingsCalculator`, so `from coco_ratings.rating import RatingsCalculator`
  still works (`tests/test_rating.py` relies on it).
- `logging.basicConfig` is gone from `rating.py`. `coco_ratings/logging_setup.py`
  holds `configure_file_logging()`, called from `cli.main()`, so the CLI and GUI
  keep their debug log and importers get nothing.
- `tests/test_core_isolation.py` (5 tests) enforces the contract: no `io` in
  `sys.modules`, zero root handlers, no file written to the CWD, the public
  surface, and that the shim aliases the same class objects rather than
  shadowing them.

**Result:** golden file byte-identical, 32 engine tests + 55 Django tests pass,
ruff clean. The suite also got **~11x faster** (2.27s → 0.20s): every
`logging.debug` in the per-game rating loop had been formatting and writing to
disk on every run. Verified importable from Baxter's own venv (both projects are
on Python 3.14.3) with zero root handlers and `io` absent.

Two stray `coco_ratings.log` files under `web/` and `scripts/` are leftovers of
the old import-time behaviour and can be deleted; they are already gitignored.

### How the core is shared

Baxter depends on this repo as a **git dependency tracking `main`**:

```toml
# baxter/pyproject.toml
dependencies = ["coco-ratings", ...]

[tool.uv.sources]
coco-ratings = { git = "https://github.com/cocoscrabble/ratings.git", branch = "main" }
```

`uv.lock` still pins an exact commit, so Baxter's builds are reproducible; an
upgrade is a deliberate `uv lock --upgrade-package coco-ratings`. No tagging
ceremony and no PyPI account for a two-consumer package.

Why a git dep and not a path dep: Baxter builds in Docker (`uv sync` inside the
image), so `../ratings` is outside the build context and cannot resolve. Both
repos are public, so the clone needs no credentials at build time, and this repo
is ~1.2 MB.

**What this obliges us to:** `main` here is now an input to Baxter's build.
Anything that breaks `coco_ratings.core`'s import surface or its isolation
breaks Baxter's next lock refresh — which is exactly what
`tests/test_core_isolation.py` is for.

---

## Phase 2 — Number-keyed results, alongside the name-keyed ones

Today `results/*-results.csv` identifies players by name, and `build_db`
(`web/ratings/management/commands/build_db.py:40`) matches computed players to
`players.Player` rows with `{p.name: p for p in Player.objects.all()}`. Two
players who share a name are one player to this pipeline.

**The name-keyed format is not going away yet.** It is a direct export from a
Google Form linked to a spreadsheet — which is also why `Submitted On` is a Form
timestamp in Excel serial form — and Baxter's exporter was written to match that
export byte-for-byte, which is why the two already agree. So this phase does
**not** convert the corpus. It teaches the readers to accept a number-bearing
file *as well*, and dispatch on what the file actually contains.

The Form path **cannot** be made number-keyed: players type their own names into
the form, so it has no access to a player number and never will. That is the
point of `data/players.csv` (Name → Number) — it is what joins a name-keyed file
to a canonical player before anything reaches the DB, and it absorbs the
spelling variance that self-typed names inevitably carry. Its role is unchanged
and stays load-bearing for as long as the Form exists.

### 2a. Format

Number columns are an **optional addition**. Both shapes are valid input:

```
legacy (unchanged, still produced):
  Submitted On, Round, Winner, Winners Score, Opponent, Opponents Score

number-bearing (Baxter, once its identity work lands):
  Submitted On, Round, Winner, Winner Number, Winners Score,
                Opponent, Opponent Number, Opponents Score
```

Same for the ratings file: `Name, Rating` stays valid, `Name, Number, Rating` is
the number-bearing form. The pair is produced together, so a reader should not
assume the two halves agree about which form they are in — check each.

Numbers are canonical (zero-padded, via `canonical_player_number`).

### 2b. Readers dispatch on the header

`ResultCSVReader` and `CSVRatingsFileReader` in `io.py` inspect the header once
and pick a path:

- **number columns present** → the number is the identity. No name lookup, no
  ambiguity, and two same-named players stay two players.
- **number columns absent** → today's behaviour exactly: key on name, joined to a
  canonical player through `data/players.csv`.

Keep the dispatch at the header, not per row: a file that mixes the two is
malformed and should say so rather than silently half-resolving. Make the chosen
path visible in the reader's output (a `keyed_by` attribute or similar) so
`build_db` can report which corpus is which, and so the eventual deprecation has
a way to measure progress.

`build_db` prefers a number when the pipeline carried one and falls back to its
current name match otherwise. Its "unmatched players" report should say which
key failed — a name that `data/players.csv` doesn't cover is a different problem
from a number that no `Player` row has.

### 2c. What is explicitly not happening

- **The 256 existing files are not rewritten.** They are the Form export's
  output and must keep working untouched.
- **Name matching is not deleted.** It is a supported path for as long as the
  other producer exists, not a fallback waiting to rot.

When the Form flow is finally retired — which means Baxter taking over result
collection, since the Form cannot be upgraded — backfilling the corpus and
dropping the name path become available as cleanup. That is not this work, and
doing it early would break a producer that is still in service.

### 2d. Verification

`tests/test_golden.py` must be **byte-identical** — trivially so, because no
input file changes. Here the golden is a regression net proving the reader
refactor did not disturb the legacy path, not evidence about a migration.

Add reader tests over both header shapes, including a number-bearing file with
two same-named players resolving to two distinct identities — the case the
legacy format cannot express. Confirm `make test` passes both suites and that
`build_db` still reports zero unmatched players.


## Phase 3 — Roster pull

Baxter needs each entrant's `rating`, `deviation`, `career_games` and
`last_played` before an event, and must then be able to run with no connection
here. `ratings.CurrentRating` already holds exactly those four fields.

### 3a. Endpoint

`GET /api/roster/` returning the `coco.roster/1` document specified in the
program plan: `player_number`, `name`, `rating`, `deviation`, `career_games`,
`last_played` for every player, with `rating: null` for players who have no rated
games yet.

- Token-authenticated. The roster is public-ish data already (player pages and
  the search JSON are public), but this is a bulk endpoint and should not be
  anonymous. **Nothing from `PlayerDetails` may appear here** — it is the only
  private data the site holds, and `PlayerDetailsPrivacyTest` exists to keep it
  out of public surfaces. This endpoint is another such surface.
- No pagination. The roster is 245 rows.

### 3b. Snapshot file

The same document, downloadable from `/manage/`, for offline events. Baxter
imports either through one code path, so this is the lower-risk half to build
first — it needs no auth design at all.

**Verification:** a test asserting the payload shape and that no `PlayerDetails`
field appears in it; an unrated player serializes with `rating: null`; the
snapshot file and the endpoint produce identical bytes for the same DB state.

---

## Phase 4 — Assigning numbers to new players

The workflow the program plan settles on is: a director runs an event with a
guest, and afterwards an admin creates that player *here* so Baxter can resolve
its `T-` placeholder onto a real number and unblock its export.

`/manage/players/add/` already does this one at a time, which may be enough. If
it proves tedious in practice, the smallest useful addition is a bulk-add form
accepting a pasted list of names — deliberately **not** an API, because keeping
number assignment a human decision in this system is the thing that stops
provisional identities leaking in.

Treat this phase as optional and driven by real use, not built up front.

---

## Sequencing

Phase 1 first: it is small, it fixes a live bug in this repo (the 1.68 GB log),
and it is what unblocks Baxter's live-ratings work. Phases 2 and 3 are
independent of each other and of Phase 1. Phase 4 waits for evidence it is
needed.

## Out of scope

- Any ingest endpoint. Baxter emits native files; a human commits them and reruns
  `build_db`. The committed-files-are-source-of-truth model stays.
- Any minting API. Numbers are assigned by an admin here, never by Baxter.
- Rewriting the 256 existing `results/*.csv` files, or removing the name-keyed
  reader path. Both wait on the Google Form flow being retired (Phase 2c).
- `complete-ratings-list.csv` (`Name,Rating,Deviation,Games played`) stays
  name-keyed and carries no number. It is not part of the Baxter contract — the
  pull reads the database.
