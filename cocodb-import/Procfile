web: uv run gunicorn cocodb.wsgi --bind 0.0.0.0:$PORT --workers 2
release: uv run manage.py migrate
