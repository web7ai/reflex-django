"""Settings for admin auto-mount ordering tests (reflex_django before admin)."""

from __future__ import annotations

SECRET_KEY = "reflex-django-admin-order-test"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "reflex_django",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
]

RX_AUTO_MOUNT = True
RX_CONFIG = {"app_name": "demo"}

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "reflex_django_tests.test_auto_mount_admin_order_urls"

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
