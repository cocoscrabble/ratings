# Convenience targets. Requires uv (see CLAUDE.md); the web extra pulls in Django.
.PHONY: run test

# Dev server port; override with `make run PORT=9000`.
PORT ?= 8001

# Start the Django dev server on a freshly seeded DB: migrate, import the
# published players (so build_db can match them), rebuild the ratings projection.
run:
	uv run --extra web python web/manage.py migrate --noinput
	uv run --extra web python web/manage.py import_csv --current data/published-ratings.csv
	uv run --extra web python web/manage.py build_db
	uv run --extra web python web/manage.py runserver $(PORT)

# Run all tests: the engine's unittest suite and both Django apps' suites.
test:
	uv run --extra web python -m unittest
	uv run --extra web python web/manage.py test players ratings
