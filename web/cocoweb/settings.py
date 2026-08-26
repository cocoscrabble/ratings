"""Django settings for the CoCo ratings web app.

The database is a rebuildable projection of the repo's results/ folder (see the
build_db management command), so nothing here is a source of truth. Secrets and
paths are environment-overridable for deployment (Dokku).
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Env var names match the VPS Ansible convention (configure-app.yml sets
# SECRET_KEY / ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / DEBUG unprefixed).
DEV_SECRET_KEY = "dev-insecure-key-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
DEBUG = os.environ.get("DEBUG", "True") == "True"

# The secret key signs session cookies, so with the dev fallback in place
# anyone can forge a staff session. ../vps configure-app.yml sets SECRET_KEY,
# but a missing one must fail loudly rather than quietly serve a public site
# with a key that is in this file. Raised during release (migrate), which
# aborts the deploy and leaves the running version up.
if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY must be set in the environment when DEBUG is False."
    )
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# Shared static token for the roster endpoint (see ratings.views.roster_api).
# The roster is names and ratings — already public one page at a time — so a
# token is about not serving a bulk dump to anonymous crawlers, not about
# guarding secrets. Deliberately *not* defaulted: an unset token disables the
# endpoint rather than opening it, so a deploy that forgets to set one fails
# closed. There is no dev fallback for the same reason.
ROSTER_API_TOKEN = os.environ.get("ROSTER_API_TOKEN", "")
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "players",
    "ratings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cocoweb.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cocoweb.wsgi.application"

# In production Dokku injects DATABASE_URL (dokku-postgres); locally there's no
# DATABASE_URL so we fall back to SQLite. The DB is a rebuildable projection of
# results/ either way, so the backend is an implementation detail.
if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.config(conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("COCO_DB_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

_VALIDATORS = "django.contrib.auth.password_validation"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"{_VALIDATORS}.UserAttributeSimilarityValidator"},
    {"NAME": f"{_VALIDATORS}.MinimumLengthValidator"},
    {"NAME": f"{_VALIDATORS}.CommonPasswordValidator"},
    {"NAME": f"{_VALIDATORS}.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]  # web/static (players app css/js/logo)

# WhiteNoise serves static (admin + players app css/js) from the container. The
# hashed/manifest backend needs collectstatic to have run (it does in the Docker
# build), so use it only in production; dev and tests use plain storage so
# {% static %} works without a manifest.
_TESTING = "test" in sys.argv
if DEBUG or _TESTING:
    _staticfiles_backend = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    _staticfiles_backend = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": _staticfiles_backend},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# A custom user model from the start, so later additions (profile fields, or
# switching the login identity to email) are ordinary migrations instead of a
# swap of AUTH_USER_MODEL on a populated database. See accounts/models.py.
AUTH_USER_MODEL = "accounts.User"

# Auth for the players /manage section. Note /manage is gated on is_staff, not
# merely on being logged in (accounts.decorators.staff_required).
LOGIN_URL = "/manage/login/"
LOGIN_REDIRECT_URL = "/manage/players/"
LOGOUT_REDIRECT_URL = "/"

# There is no mail service configured for this deployment, so there is no
# self-service password reset: a superuser resets passwords in /django-admin/.
# Wiring one up later means setting EMAIL_* here and adding Django's
# PasswordReset* views to players/urls.py.

# Session cookies carry staff privileges, so outside of dev they must never
# travel in clear text. Dokku terminates TLS and forwards the original scheme,
# which is what lets Django tell an HTTPS request from an HTTP one.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"
