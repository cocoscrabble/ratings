release: python web/manage.py migrate --noinput && python web/manage.py build_db
web: gunicorn --chdir web cocoweb.wsgi --bind 0.0.0.0:8000 --workers 3
