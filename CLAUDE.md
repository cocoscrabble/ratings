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
    gui.py              # Tk front-ends (App, SimulationApp, File widgets)
    pipeline.py         # full-history replay/orchestrator (was all_rating.py)
    cli.py              # `coco-rate` entry point (main); __main__.py delegates here
    players.py          # PlayerDB   (name <-> CoCo id)
    tournaments.py      # TournamentDB (chronological driver)
    paths.py            # anchors data/ and results/ to the project root
scripts/                # standalone / experimental scripts (not core)
tests/                  # unittest suite, incl. golden-master test
data/  results/  docs/  testdata/   # kept at repo root
```

## Commands

Environment is managed by **uv** (this is an Arch/PEP-668 externally-managed
host, so a project venv is required — do not `pip install` into system Python).

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

**`gui.py`** — the Tk front-ends (`App`, `SimulationApp`, `File`/`FilesWidget`),
at the top of the stack. `pipeline` subclasses `App`/`SimulationApp` to wire in
the full-history replay; nothing in the engine imports `gui`.

`RatingsCalculator` holds the actual math. Two-phase per section: iteratively
solve for unrated players' seed ratings until convergence
(`calc_initial_ratings`), then rate everyone (`calc_new_rating_for_player`).
Key tunables: `beta` (rating points per point of expected spread, default 5) and
`tau`. `_player_multiplier` damps rating changes for established/high-rated
players. Rating deviation grows with inactivity (`adjust_initial_deviation`).

**`pipeline.py`** — the orchestrator that replays history. `RatingsDB` walks
every tournament in date order, and before rating each one, `adjust_tournament`
overwrites each returning player's `init_rating`/`deviation`/`career_games` with
their carried-forward values from prior tournaments. It produces the combined
current ratings list (`complete-ratings-list.csv`) and a per-tournament report,
and holds the GUI subclasses (`App`, subclassing `gui.App`) that wire the replay
into the GUI.

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

**`results/`** — the historical corpus. Each tournament is a pair of files:
`<prefix>-results.{csv,tsv}` and `<prefix>-ratings.{csv,tsv}`. The `<prefix>`
must match the `Filename` column in `data/tournaments.csv`. Adding a tournament
means dropping in these two files and adding a row there.

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
