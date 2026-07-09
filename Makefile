# Convenience targets. Requires uv (see CLAUDE.md); the web extra pulls in Django.
.PHONY: run test

# Start the Django dev server on a freshly built DB (rebuilt from results/).
run:
	uv run --extra web python web/manage.py migrate --noinput
	uv run --extra web python web/manage.py build_db
	uv run --extra web python web/manage.py runserver

# Run all tests: the engine's unittest suite and the Django DB/view suite.
test:
	uv run --extra web python -m unittest
	uv run --extra web python web/manage.py test ratings
