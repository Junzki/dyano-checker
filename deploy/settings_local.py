"""Deployment settings overrides.

This module is NOT part of the image; it is mounted into the backend container
at `backend/config/settings_local.py` (see docker-compose.yaml) and activated
via `DJANGO_SETTINGS_MODULE=config.settings_local`. All values are driven by
environment variables so the same file works across environments.
"""

import os

from .settings import *  # noqa: F401,F403

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes", "on"}

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

REDIS_URL = os.environ.get("REDIS_URL", REDIS_URL)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DB_PATH", str(PROJECT_ROOT / "data" / "db.sqlite3")),
    }
}

STATIC_ROOT = os.environ.get("STATIC_ROOT", str(PROJECT_ROOT / "staticfiles"))

MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(PROJECT_ROOT / "media"))
