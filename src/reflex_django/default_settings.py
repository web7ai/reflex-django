"""Default Django settings used by :mod:`reflex_django` when the user has not
supplied their own ``DJANGO_SETTINGS_MODULE``.

The defaults are intentionally minimal:

- ``django.contrib.staticfiles`` is enabled so the Django admin's CSS/JS load
  in development (Reflex/granian replaces ``runserver`` so the staticfiles
  handler is wired into the ASGI app instead, see
  :func:`reflex_django.asgi.build_django_asgi`).
- ``TEMPLATES`` is configured only to the minimum required by
  ``django.contrib.admin``.
- The database URL is parsed from :class:`reflex_base.config.Config.db_url`,
  falling back to a local SQLite file in the working directory.
- The path prefixes for the API and admin mounts are stored in the settings
  module so :mod:`reflex_django.urls` can read them.
- ``REFLEX_DJANGO_AUTO_SETTINGS = True`` marks the module so the plugin can
  warn users that they should provide their own ``SECRET_KEY`` for production.

Override by setting ``DJANGO_SETTINGS_MODULE`` in the environment before any
Reflex code imports, e.g. ``DJANGO_SETTINGS_MODULE=myapp.settings``.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import unquote, urlparse


def _resolve_db_url() -> str:
    """Pick a database URL from rxconfig, env, or a sensible sqlite default.

    Returns:
        A URL string suitable for :func:`_db_config_from_url`.
    """
    env_url = os.environ.get("REFLEX_DJANGO_DATABASE_URL")
    if env_url:
        return env_url

    try:
        from reflex_base.config import get_config

        cfg = get_config()
    except Exception:
        cfg = None

    if cfg is not None and getattr(cfg, "db_url", None):
        return cfg.db_url  # pyright: ignore[reportReturnType]

    return f"sqlite:///{(Path.cwd() / 'reflex.db').as_posix()}"


_DB_ENGINES = {
    "sqlite": "django.db.backends.sqlite3",
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "mysql": "django.db.backends.mysql",
    "mariadb": "django.db.backends.mysql",
    "oracle": "django.db.backends.oracle",
}


def _db_config_from_url(url: str) -> dict[str, object]:
    """Translate a SQLAlchemy/Django-style URL into a Django DATABASES entry.

    Args:
        url: A database URL (e.g. ``sqlite:///app.db``, ``postgres://...``).

    Returns:
        A dict suitable for ``DATABASES["default"]`` in Django settings.

    Raises:
        ValueError: When ``url`` uses a scheme that Django does not support.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.split("+", maxsplit=1)[0].lower()
    engine = _DB_ENGINES.get(scheme)
    if engine is None:
        msg = (
            f"Unsupported db_url scheme {scheme!r} for Django; supported: "
            f"{sorted(_DB_ENGINES)}. Set DJANGO_SETTINGS_MODULE to your own "
            "settings module to customize."
        )
        raise ValueError(msg)

    if scheme == "sqlite":
        # sqlite:///relative.db or sqlite:////abs/path.db
        raw = unquote(parsed.path or "")
        if raw.startswith("/") and not raw.startswith("//"):
            name = raw[1:] if Path(raw).is_absolute() is False else raw
        else:
            name = raw
        if not name:
            name = (Path.cwd() / "reflex.db").as_posix()
        return {"ENGINE": engine, "NAME": name}

    return {
        "ENGINE": engine,
        "NAME": (parsed.path or "").lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port) if parsed.port else "",
    }


# Marker for the plugin so it can warn users running with the bundled defaults.
REFLEX_DJANGO_AUTO_SETTINGS = True

# Path prefix used by reflex_django.urls (kept in sync with the plugin).
REFLEX_DJANGO_ADMIN_PREFIX = os.environ.get("REFLEX_DJANGO_ADMIN_PREFIX", "/admin")

# Reflex-side context (JSON-serializable dicts only). See reflex_django.reflex_context.
REFLEX_DJANGO_CONTEXT_PROCESSORS: tuple[str, ...] = ()

# When True and REFLEX_DJANGO_CONTEXT_PROCESSORS is empty, collect_reflex_context
# runs TEMPLATES[*].OPTIONS["context_processors"] and drops / adapts non-JSON keys.
REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS: bool = False

# Redirect target for :func:`reflex_django.django_login_required` when anonymous.
REFLEX_DJANGO_LOGIN_URL = "/login"

# Canned Reflex auth pages (login, register, password reset). See reflex_django.auth.
REFLEX_DJANGO_AUTH = {
    "ENABLED": True,
    "SIGNUP_ENABLED": True,
    "PASSWORD_RESET_ENABLED": True,
    "LOGIN_URL": "/login",
    "SIGNUP_URL": "/register",
    "PASSWORD_RESET_URL": "/password-reset",
    "PASSWORD_RESET_CONFIRM_URL": "/password-reset/confirm/[uid]/[key]",
    "LOGIN_REDIRECT_URL": "/",
    "LOGOUT_REDIRECT_URL": "/login",
    "SIGNUP_REDIRECT_URL": "/login",
    "REDIRECT_AUTHENTICATED_USER": "/",
    "LOGIN_FIELDS": ["username"],
    "EMAIL_REQUIRED": False,
    "USERNAME_MIN_LENGTH": 1,
    "PASSWORD_MIN_LENGTH": 8,
    "MESSAGES": {
        "invalid_credentials": "Invalid username or password.",
        "username_taken": "That username is already taken.",
        "email_taken": "That email is already registered.",
        "password_mismatch": "Passwords do not match.",
        "password_too_short": "Password is too short.",
        "username_required": "Username is required.",
        "email_required": "Email is required.",
        "reset_email_sent": (
            "If an account exists for that address, you will receive reset instructions."
        ),
        "reset_success": "Your password has been set. You can sign in now.",
        "reset_invalid_link": "This reset link is invalid or has expired.",
        "registration_success": "Account created successfully.",
    },
}

# Origin for password-reset links when no HTTP request is bound (optional).
# REFLEX_DJANGO_SITE_ORIGIN = "http://localhost:3000"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"

# When True, :meth:`reflex_django.DjangoUserState.sync_from_django` loads group names.
REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS = False

# When True and ``USE_I18N``, :class:`reflex_django.middleware.DjangoEventBridge`
# runs :meth:`django.middleware.locale.LocaleMiddleware.process_request` on the
# synthetic request so ``translation.activate`` matches Django HTTP behavior.
REFLEX_DJANGO_I18N_EVENT_BRIDGE = True

# Static files (CSS, JavaScript, images) — served by ASGIStaticFilesHandler in
# DEBUG mode, or from STATIC_ROOT (populated by ``reflex django collectstatic``)
# otherwise. The default path is mirrored in the plugin so the dispatcher
# forwards ``/static/*`` to Django.
STATIC_URL = os.environ.get("REFLEX_DJANGO_STATIC_URL", "/static/")
STATIC_ROOT = os.environ.get(
    "REFLEX_DJANGO_STATIC_ROOT",
    str(Path.cwd() / ".reflex-django" / "staticfiles"),
)

SECRET_KEY = os.environ.get("REFLEX_DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)

DEBUG = os.environ.get("REFLEX_DJANGO_DEBUG", "1") not in {"0", "false", "False"}

ALLOWED_HOSTS = os.environ.get("REFLEX_DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = os.environ.get("REFLEX_DJANGO_URLCONF", "reflex_django.urls")

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
    "default": _db_config_from_url(_resolve_db_url()),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
