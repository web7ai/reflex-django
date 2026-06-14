"""Minimal Django settings used by reflex-django unit tests.

In-memory sqlite + the same INSTALLED_APPS / MIDDLEWARE as the bundled default
settings, with a deterministic SECRET_KEY so test runs are reproducible.
"""

from __future__ import annotations

SECRET_KEY = "reflex-django-test-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
]

# Tests assume the legacy Vite-HMR default for ``run_reflex``. The library
# default is now ``True`` (from-build on by default) — individual tests that
# need the new behaviour set it explicitly via ``monkeypatch.setattr``.
RX_SERVE_FROM_BUILD = False
RX_AUTO_MOUNT = False

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]

ROOT_URLCONF = "reflex_django.django.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("de", "German"),
]

