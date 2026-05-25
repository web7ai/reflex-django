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

# ASGI routing mode for combining Reflex + Django:
# - "django_outer" (default): Django is the outer ASGI app on one port,
#   Reflex's Socket.IO/upload endpoints are mounted under Django, dev
#   mode reverse-proxies "/" to Vite. Recommended for new projects.
# - "reflex_led": Reflex is the outer ASGI app, Django is mounted by prefix.
# - "django_led": Legacy alias preserved for backward compatibility.
# - "auto": resolve from REFLEX_DJANGO_URL_ROUTING env or fall back to default.
REFLEX_DJANGO_URL_ROUTING = os.environ.get("REFLEX_DJANGO_URL_ROUTING", "auto")

# Catch-all mount prefix for :func:`reflex_django.urls.reflex_mount`.
REFLEX_DJANGO_MOUNT_PREFIX = os.environ.get("REFLEX_DJANGO_MOUNT_PREFIX", "/")

# Django-led: "package.module:create_app" returning rx.App (optional).

# Django-led: dotted modules to import so @rx.page / decorators register.
# REFLEX_DJANGO_PAGE_PACKAGES: list[str] = ["myapp.pages"]

# Reflex-side context (JSON-serializable dicts only). See reflex_django.reflex_context.
REFLEX_DJANGO_CONTEXT_PROCESSORS: tuple[str, ...] = ()

# When True, DjangoEventBridge runs context processors on every Reflex event
# (same work as AppState.load_django_context — no manual call needed).
REFLEX_DJANGO_AUTO_LOAD_CONTEXT: bool = True

# When True and REFLEX_DJANGO_CONTEXT_PROCESSORS is empty, collect_reflex_context
# runs TEMPLATES[*].OPTIONS["context_processors"] and drops / adapts non-JSON keys.
REFLEX_DJANGO_USE_TEMPLATE_CONTEXT_PROCESSORS: bool = True

# Redirect target for :func:`reflex_django.auth.decorators.login_required` when anonymous.
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

# When True, :class:`reflex_django.middleware.DjangoEventBridge` refreshes
# :class:`~reflex_django.states.AppState` auth snapshot vars on every event.
REFLEX_DJANGO_AUTH_AUTO_SYNC = True

# Deprecated. The full Django middleware chain (including LocaleMiddleware)
# now runs on every Reflex event by default; this flag is preserved as a
# no-op alias for users on older configurations.
REFLEX_DJANGO_I18N_EVENT_BRIDGE = True

# When True (default), :class:`reflex_django.middleware.DjangoEventBridge`
# runs the full ``settings.MIDDLEWARE`` chain on every Reflex event via
# :class:`reflex_django.event_handler.EventMiddlewareHandler`. Disable to
# restore the legacy lightweight bridge (only session/auth/locale ran).
REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN: bool = True

# Middleware classes to skip when running the full chain on Reflex events.
# CSRF cannot pass without a token and AsyncStreamingMiddleware is HTTP-only.
REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP: tuple[str, ...] = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
)

# When True (default), if a middleware short-circuits with a 3xx response,
# the bridge converts it into a Reflex ``rx.redirect(...)`` event so the
# browser navigates to the target. Disable to handle redirects manually.
REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE: bool = True

# When True, the event payload (handler kwargs) is fed into ``request.POST``
# of the synthetic request. Off by default — Reflex events are RPC-style,
# not form submissions, so most middleware does not look at POST.
REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD: bool = False

# Individual mirror toggles for the reactive ``DjangoUserState`` vars
# populated from the middleware chain. Disable to save delta size on apps
# that do not bind these in the UI.
REFLEX_DJANGO_MIRROR_MESSAGES: bool = True
REFLEX_DJANGO_MIRROR_CSRF: bool = True
REFLEX_DJANGO_MIRROR_LANGUAGE: bool = True

# When True (default), Django's catch-all view reverse-proxies "/" to the
# Vite dev server in DEBUG mode. Set to False (or env REFLEX_DJANGO_DEV_PROXY=0)
# to serve the compiled SPA directly even in DEBUG.
REFLEX_DJANGO_DEV_PROXY: bool = True

# When True (default), Django's catch-all view runs the Reflex SPA's
# ``index.html`` through Django's template engine with
# :class:`~django.template.RequestContext`. This makes ``{{ request.user }}``,
# ``{{ csrf_token }}``, ``{{ messages }}``, ``{{ LANGUAGE_CODE }}`` and any
# ``settings.TEMPLATES[0]["OPTIONS"]["context_processors"]`` keys usable
# directly inside the SPA shell (both in dev and prod). Set to ``False`` to
# serve the file verbatim. Non-HTML responses (JS bundles, CSS, source maps,
# images) are always served verbatim regardless of this setting.
REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE: bool = True

# Whether the "Built with Reflex" badge is shown in the SPA. Reflex's
# upstream default is True; reflex-django flips it to False because most
# Django-first apps ship their own branding. To re-enable, set this to True
# in your Django settings (or pass it via
# ``reflex_mount(rx_config={"show_built_with_reflex": True})``).
REFLEX_DJANGO_SHOW_BUILT_WITH_REFLEX: bool = False

# Additional reserved Reflex path prefixes for the outer dispatcher
# (advanced; usually not needed). Combined with the defaults in
# :data:`reflex_django.django_outer_dispatcher.DEFAULT_RESERVED_REFLEX_PREFIXES`.
REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES: tuple[str, ...] = ()

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
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
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
