# Dokku builds this image (cocodb_builder: dockerfile in the vps Ansible config).
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# Install third-party deps first for layer caching (project itself installed
# after the source is copied).
COPY pyproject.toml uv.lock ./
RUN uv sync --extra web --no-dev --frozen --no-install-project

# App source (engine, web app, and the results/ + data/ source of truth).
COPY . /app
RUN uv sync --extra web --no-dev --frozen

ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=cocoweb.settings \
    PYTHONUNBUFFERED=1 \
    COCO_DATA_DIR=/app/data \
    COCO_RESULTS_DIR=/app/results

# Bake admin/static assets into the image (WhiteNoise serves them). No DB needed.
# DEBUG=False so this uses the manifest storage backend and writes
# staticfiles.json — runtime (DEBUG=False) requires it, and without it every
# {% static %} render 500s. DEBUG defaults to True, so it must be forced here.
RUN DEBUG=False python web/manage.py collectstatic --noinput

EXPOSE 8000

# Fallback if no Procfile web process; Dokku uses the Procfile's `web:` line.
CMD ["gunicorn", "--chdir", "web", "cocoweb.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3"]
