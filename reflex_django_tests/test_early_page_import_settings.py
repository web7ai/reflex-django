"""Settings for @page import before admin autodiscover regression."""

from __future__ import annotations

SECRET_KEY = "reflex-django-early-page-import-test"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "reflex_django",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "reflex_django_tests.test_early_page_import_app",
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
                "django.template.context_processors.request",
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
    }
}

USE_TZ = True