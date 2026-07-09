---
name: Dev tooling preferences
description: Preferred dev tools for the cocodb project
type: feedback
---

Use `uv` for dependency management (pyproject.toml, not requirements.txt). Run Django commands with `uv run manage.py ...`.

Allow SQLite for local testing (default DATABASE_URL to sqlite:///db.sqlite3 in settings). Use Postgres only in production via DATABASE_URL env var.

Format and lint all Python code with ruff (add as dev dependency, configure in pyproject.toml).

**Why:** User explicitly specified these tools when implementation was about to start.
**How to apply:** Every new Python project in this repo should use this toolchain from the start. Always include ruff in dev dependencies and run it before committing.
