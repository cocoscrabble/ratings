# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Rating software for CoCo (crossword game) tournaments. Ratings use the Norwegian
rating system (spread-based Glicko-style; see `docs/norwegian-rating.pdf`). There
is no database yet — everything is CSV/text files carried forward by re-running
the full tournament history from scratch each time.

## Commands

```bash
# Run the tests (from the repo root — the tests use package-relative imports,
# so `unittest discover` inside tests/ will fail)
python -m unittest

# Lint (config lives only in .ruff_cache; ruff is run with defaults)
ruff check .

# Rate the full history and write the current combined ratings list to a file
python all_rating.py <output.txt>

# Launch the Tk GUI (no argument)
python all_rating.py
```

**Do not run `rating.py` directly.** Its `__main__` is intentionally stubbed to
print a reminder and exit — `all_rating.py` is the real entry point because a
single tournament can only be rated in the context of everything before it.

## Architecture

The core insight: a player's new rating depends on their opponents' *current*
ratings, so ratings are always recomputed by replaying the entire tournament
history in chronological order. There is no persisted rating state between runs.

**`rating.py`** — the rating engine and file-format layer for a *single*
tournament. Everything funnels through the `Tournament` class, which wires
together three concerns, each with pluggable reader/writer classes selected by
file extension:

- **Results readers** (`ResultCSVReader` for `.csv`/`.tsv`, `TouReader` for
  AUPAIR `.tou`) parse game-by-game results into `Player` objects grouped into
  `Section`s. `.csv` results carry no metadata, so name/date must be passed in;
  `.tou` files embed them.
- **Ratings-file readers** (`CSVRatingsFileReader`, `RTFileReader`) load the
  pre-tournament rating list into a `PlayerList`.
- **Writers** (`TabularResultWriter` → `.txt`, `CSVResultWriter` → `.csv`,
  `TouResultWriter` → `.tou`, `RTFileWriter` → `.RT`) emit results/ratings.

`RatingsCalculator` holds the actual math. Two-phase per section: iteratively
solve for unrated players' seed ratings until convergence
(`calc_initial_ratings`), then rate everyone (`calc_new_rating_for_player`).
Key tunables: `beta` (rating points per point of expected spread, default 5) and
`tau`. `_player_multiplier` damps rating changes for established/high-rated
players. Rating deviation grows with inactivity (`adjust_initial_deviation`).

**`all_rating.py`** — the orchestrator that replays history. `RatingsDB` walks
every tournament in date order, and before rating each one, `adjust_tournament`
overwrites each returning player's `init_rating`/`deviation`/`career_games` with
their carried-forward values from prior tournaments. It produces the combined
current ratings list (`complete-ratings-list.csv`) and a per-tournament report,
and hosts the GUI (`App`, subclassing `rating.App`).

**`players.py` / `tournaments.py`** — thin CSV-backed lookup tables in `data/`.
`PlayerDB` (`data/players.csv`) maps player name ↔ CoCo id. `TournamentDB`
(`data/tournaments.csv`) is the chronological list that drives the replay; its
`Filename` column is the prefix used to locate result/rating files.

**`results/`** — the historical corpus. Each tournament is a pair of files:
`<prefix>-results.{csv,tsv}` and `<prefix>-ratings.{csv,tsv}`. The `<prefix>`
must match the `Filename` column in `data/tournaments.csv`. Adding a tournament
means dropping in these two files and adding a row there.

## File formats

- **Results CSV** columns: `Submitted On, Round, Winner, Winners Score, Opponent, Opponents Score` (header row is skipped).
- **Ratings CSV** columns: `Name, Rating, Email` (rating `0` ⇒ unrated).
- `.tou` and `.RT` are legacy AUPAIR formats supported for interop; readers/writers
  live in `rating.py`. Extension determines the parser, so name files correctly.
- Player identity is by exact name string across all files — name mismatches
  create phantom unrated players, so consistency matters.

## Notes

- Byes/forfeits are filtered by name (see the `byes` set in `Tournament.output_ratfile`) and skipped in rating math.
- `output_active_ratfile` reads a `removed_people.txt` (deceased/removed players) that is not checked in.
- The repo root accumulates scratch output files (`*.csv`, `*.txt`, logs) from runs; these are working artifacts, not source.
