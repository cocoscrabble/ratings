FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies (production only, no dev group)
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

# Copy source
COPY . .

# Collect static files
RUN uv run manage.py collectstatic --noinput

EXPOSE 8000

CMD ["uv", "run", "gunicorn", "cocodb.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2"]
