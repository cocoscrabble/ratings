# Plans

Design and implementation notes for larger pieces of work. **New plans go here**
(`plans/*.md`), not in the repo root and not in `docs/`.

The split: `plans/` is written for whoever picks the work up next — including
Claude — so a document here states the goal, the decisions and why they were
made, and a phased breakdown with per-phase verification. Code references are
pinned to a commit, since they drift. `docs/` holds static human-oriented
reference material (currently the Norwegian rating system paper). Repo-wide
orientation lives in `CLAUDE.md`, which is loaded every session; a plan is the
place for depth that would bloat it.

Current documents:

- `baxter-integration.md` — the coco-ratings half of integrating with **Baxter**
  (`../baxter`, the tournament manager): extract a dependency-free
  `coco_ratings.core` so Baxter can project live in-tournament ratings with
  *this* project's math instead of a second implementation; teach the result
  readers to accept number-keyed files alongside the Google Form's name-keyed
  ones; and expose the roster with current ratings so Baxter can pull seeds
  before an event and then run with no connection here. **Phase 1 implemented**
  (the core extraction); phases 2–4 not started. The program-level design
  spanning both repos is `../baxter/plans/PLAN_COCO_PROGRAM.md`.
- `auth-migration.md` — the record of swapping to a custom user model
  (`accounts.User`) and gating `/manage` on `is_staff`. **Complete** (August
  2026, `b8e45dc`); kept because the reason for the `accounts` app and the
  manual `LogEntry` database step it required are not visible in a diff.
- `rating-history.md` — archaeology, not a plan: the committed run of
  `scripts/rating_history.py` over the full history, identifying which code
  changes actually moved someone's rating (4 of 200 commits touching `.py`).
  Regenerate it after a change that moves ratings.
