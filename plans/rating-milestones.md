# Plan: rating milestones (freeze published ratings; change only the future)

**Status: proposed** — drafted 2026-10-20; open questions settled the same day. Code references pinned at ratings
`f93cbdf`. Related: `../baxter/plans/PLAN_UNPLAYED_GAMES.md`, whose
rating-changing phase this plan turns into a future-only change.

## Goal

Stop amending historical ratings. A rating that has been published stays
published: the one a player had after a given tournament, and the one they
carry into the next. Changing the rating math, or upgrading Python, must
affect only tournaments rated after the change.

Today every deploy replays the whole history from scratch (`build_db` →
`pipeline.process_old_results`). So **anything** that changes the engine's
output rewrites every rating back to 2021. That includes a math fix, a reader
change, a data correction in an old file, and even a CPython upgrade (the
golden test notes that its values only reproduce on a matching interpreter).
`plans/rating-history.md` records four such rewrites so far.
`PLAN_UNPLAYED_GAMES` decision 4 would be a fifth, moving 128 players by 1–3
points.

## Decision 1: freeze data, not code

Two ways to stop the churn:

- **Checkpoint the code**: keep every past version of the engine and rate each
  tournament with the version that was current when it was published.
  **Rejected.** The repo would need several engines importable at once, with
  their dependencies. It would still churn on an interpreter upgrade, because
  the golden values are only reproducible on a matching CPython. And "which
  code rated this tournament" becomes a second history to maintain beside the
  results.
- **Checkpoint the data** (chosen): commit the engine's *outputs* up to a
  point, a **milestone**, and seed the replay from them. Tournaments after
  the milestone are rated by the current code. Tournaments before it are
  never rated again, whatever the code does.

The replay mechanism stays. It just stops starting from 2021: the milestone is
its starting state.

## Decision 2: what a milestone freezes, and what it does not

A rule follows from the unplayed-games decisions: **the rating formula's
inputs and outputs are frozen; everything else is derived from the results
files on every build.**

| Frozen at the milestone | Derived from results files every build |
|---|---|
| per tournament: `old_rating`, `new_rating`, `old_deviation`, `new_deviation` | per tournament: wins, losses, spread |
| carried state: `rating`, `deviation`, `last_played`, rated games (the multiplier's input) | `career_games`, which includes byes and forfeits |
| identity aliases (`RatingsDB.aliases`, name → number) | |

Records stay correctable. When `PLAN_UNPLAYED_GAMES` phase 6 backfills a bye
row into a pre-milestone file, the player's W/L and career games update on the
next build. Their ratings do not move, because ratings are not recomputed for
frozen tournaments.

**Prototype result (scratch, not committed).** The carried state is exactly
`RatingsDB.players` (name, rating, deviation, games, last_played, number) plus
`RatingsDB.aliases`. This was checked by writing that state to CSV at a cut
date, reading it back into a fresh `RatingsDB`, and replaying only the later
tournaments. The cuts were 2024-06-30, 2025-12-31 and 2026-08-01. All three
reproduced the full replay **exactly**: 0 mismatches in final state and 0 in
post-cut per-tournament reports. Ratings are ints and deviations are already
rounded to 2 dp, so a CSV round-trip loses nothing. Today's sizes are 250
players and 1,609 history rows.

## Decision 3: the milestone's files

One directory, `milestone/` at the repo root next to `results/`:

- `manifest.json`:
  - `format`: the format version.
  - `through`: the filename of the last frozen tournament.
  - `cut_at`: the date the milestone was cut.
  - `code_rev`: the commit that produced it.
  - `python`: the interpreter version.
  - `beta`: the rating parameter used.
  - `frozen`: every frozen tournament's filename, with the sha256 of its
    results file.
  - `amendments`: see decision 5.
- `state.csv`: one row per carried player. Columns are key, name, number,
  rating, deviation (`repr`, exact), rated_games, last_played.
- `aliases.csv`: name → number.
- `history.csv`: one row per (tournament filename, player key, coco_id) with
  the four frozen rating fields.

**There is only ever one milestone.** Cutting a new one rewrites the directory
as a superset of the old one; git keeps the old ones. The cutting command
refuses to change any existing `history.csv` row, so moving a milestone
forward can only add frozen history, never alter it.

**Cutting often costs no accuracy.** A milestone stores exactly the values the
engine carries from one tournament to the next. The engine already rounds those
itself after every tournament (ratings to ints, deviations to 2 dp, in
`calc_new_rating_for_player`), and deviation is written with `repr`, which
round-trips a Python float exactly. So a cut adds no rounding of its own, and
seeding from a milestone is bit-identical to replaying through it. The
prototype showed this (0 mismatches), and phase 1's equivalence test keeps it
true. If the engine ever stopped rounding, `repr` would still carry the full
value.

## Decision 4: when a milestone is cut, and how the rule is enforced

A single milestone only stops churn once. If it sits at T0, and tournaments A
and B are rated after it under the current code, then a math change later
re-rates A and B. They are published by then, so that is churn again. So the
rule is:

> **A change that moves any published rating must cut a milestone first.**

Enforce it with **`tests/test_post_milestone.py`**, a characterization test
like golden, but over real data. It rates everything after the milestone and
diffs against a committed `milestone/pending.csv`, the expected ratings of
the not-yet-frozen tournaments. Then:

- **Adding a tournament** changes `pending.csv` because there are new rows.
  Regenerate it, as with golden today (`UPDATE_PENDING=1`). The diff shows
  only the new tournament's rows, plus nothing else, since earlier pending
  tournaments are unaffected by a later one.
- **Changing the math** fails the test, because existing pending rows change.
  The fix is not to regenerate. Cut a milestone on `main` *before* the change
  (`coco-rate milestone`), which empties `pending.csv`, then land the change.
  The test message says exactly that.

Unlike golden, this test **runs in CI**. It doesn't depend on the CPython
patch version in the same way, because the pending set is small and is
regenerated whenever a milestone is cut. If an interpreter upgrade moves a
pending row, that is also a reason to cut a milestone first.

**Cadence (settled):** cut the first milestone now, then **every time the
ratings code changes** in a way that moves pending ratings, as enforced above.
There is no periodic cut.
Cutting after every tournament addition would also work, and would make
corrections to recent tournaments require an explicit rewind. Not cutting
that often leaves a window in which a results file that turns out wrong can
still be fixed and re-rated normally. That is useful, since errors are
usually found within weeks.

## Decision 5: frozen results files may change, but only on the record

The backfill in `PLAN_UNPLAYED_GAMES` will edit pre-milestone files. That is
allowed, since records are derived (decision 2), but it must be deliberate.
`tests/test_milestone.py` checks each frozen tournament's results-file hash
against the manifest. A mismatch fails CI unless `manifest.amendments` has an
entry `{filename, sha256, date, reason}` for the new content. The rating
fields in `history.csv` are never touched by an amendment.

The other ways frozen history can be disturbed, and what happens:

| Change | Behaviour |
|---|---|
| A frozen tournament's row disappears from `tournaments.csv` | error |
| A frozen row's `Date` / `Order` changes | allowed, display only; frozen tournaments are not re-ordered |
| **A new tournament dated on or before `through`**, e.g. an old event found later; "Hood River Open" is already listed with no results file | error until listed in `manifest.late_additions`; it is then rated as the first post-milestone tournament(s), against the milestone state, keeping its own date for display |
| `ratings` file of a frozen tournament changes | ignored; it only seeds first appearances, which are frozen |
| `players.csv` rename / number change | `history.csv` carries key and coco_id; `build_db` matches by number first, then name, as it already does |

**Hazard for late additions:** `Player.adjust_initial_deviation` uses
`(tournament_date - last_played).days`. For a late addition that is negative,
and over about 225 days it makes the square root's argument negative, which
raises. Clamp inactivity at zero for that case. Deviation should not shrink
for playing "in the past".

## Decision 6: what still replays from scratch

- `process_old_results(milestone=None)` keeps the full replay. Simulations
  (`run_simulation`, beta sweeps), `scripts/rating_history.py`, and the golden
  test use it: they are about the *engine*, not the published numbers.
  `process_old_results()` defaults to the milestone.
- **`test_golden` becomes an engine test only.** Regenerating it no longer
  means published ratings moved. Say so in CLAUDE.md, and keep its cutoff
  before the milestone so it never needs post-milestone data.
- `build_db` and `coco-rate <output.csv>` use the milestone.
- `web/ratings/tests.py` (DB == engine) compares against the
  milestone-seeded engine.
- Baxter is unaffected. Its live projection uses the current `core` for an
  in-progress tournament, which is future by definition. Its roster seeds come
  from `CurrentRating`, which the milestone feeds. Its corpus test rates single
  tournaments with the same code on both sides.

## Phases

### Phase 0: establish what is actually published

Production is `origin/main`, because a push to GitHub deploys (CI runs, then
`dokku/github-action` deploys). So the published numbers are a replay at
`origin/main`, provided its last deploy succeeded. A failed deploy leaves the
previous release running. Check that the latest CI run on `main` is green
(`gh run list --branch main --limit 1`), and cut from exactly that commit.

As a one-off check before the first cut, compare that replay with
production's `CurrentRating` and `TournamentResult` (a `dumpdata` export).
This confirms that nothing on the server comes from anywhere other than
`results/`.

*Verify:* the replay at the deployed commit equals production's tables
exactly. If it doesn't, stop and find out why before freezing anything.

### Phase 1: the mechanism, cut nothing yet

- `coco_ratings/milestone.py`: `Milestone.load(dir)`, `Milestone.cut(ratingsdb,
  through, ...)`, writers and readers for the four files, and hash checking.
  It belongs to the engine side, not `core`.
- `RatingsDB.from_milestone(m)` seeds `players`, `aliases` and the frozen
  `report` rating fields.
- `pipeline.process_old_results(milestone=...)`:
  - skips tournaments in `frozen`;
  - runs a **record pass** over frozen tournaments: parse only, which fills
    W/L, spread and career games into the report beside the frozen ratings;
  - rates the rest;
  - fails on any decision-5 violation.
- `coco-rate milestone [--through FILENAME]` cuts or advances one, refusing to
  alter existing history rows.
- Tests:
  - **seeding equivalence**: the prototype above, made permanent. Cut
    in-memory at several points in the golden prefix and assert that seeded
    equals full replay. This is what catches a future piece of carried state
    that someone forgets to put in the milestone.
  - every decision-5 row;
  - the late-addition deviation clamp.

*Verify:* `make test`; with no `milestone/` directory, everything behaves as
today.

### Phase 2: cut the first milestone

Run `coco-rate milestone` at the phase-0 revision, through the latest
published tournament. Commit `milestone/` and an empty `pending.csv`. Add
`test_post_milestone`, document milestones in CLAUDE.md (architecture and
"Commands"), and update `plans/rating-history.md` to say that history before
the milestone can no longer move.

*Verify:* `build_db` locally gives tables identical to production's (phase-0
export). Then make a deliberate math change on a branch, such as `beta=5.1`:
the frozen history is unchanged, and `test_post_milestone` fails only after a
new tournament is added.

### Phase 3: the unplayed-games work, now future-only

`PLAN_UNPLAYED_GAMES` phases 1–2 (bye not a player; rated vs career games) land
**after** the milestone. Phase 1 is rating-neutral. Phase 2 changes only
post-milestone ratings, so the 128-player rewrite of history no longer
happens. The milestone's `rated_games` column should be the played-only
count, computed from the files at cut time. It feeds the multiplier for the
future, and published ratings are already frozen, so correcting the count
rewrites nothing. The backfill (phase 6) becomes `amendments`.

## Settled questions

- **Canonical numbers:** production's. The first milestone freezes what
  cocodb serves, not what `main` computes.
- **Cadence:** a new milestone every time the ratings code changes. Cutting
  often has no accuracy cost (decision 3).
