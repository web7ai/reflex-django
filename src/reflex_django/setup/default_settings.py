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
  module so :mod:`reflex_django.django.urls` can read them.
- ``RX_AUTO_SETTINGS = True`` marks the module so the plugin can
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
    env_url = os.environ.get("RX_DATABASE_URL")
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
RX_AUTO_SETTINGS = True

# Base URL of an optional external Django HTTP server for split-process dev.
# When unset, Django is mounted in the Reflex backend during ``run_reflex``.
RX_PROXY_SERVER = os.environ.get("RX_PROXY_SERVER", "")

# Catch-all mount prefix for :func:`reflex_django.django.urls.reflex_mount`.
RX_MOUNT_PREFIX = os.environ.get("RX_MOUNT_PREFIX", "/")

# Append Reflex SPA catch-all to ROOT_URLCONF.urlpatterns at startup (default True).
RX_AUTO_MOUNT = os.environ.get("RX_AUTO_MOUNT", "1") not in {
    "0",
    "false",
    "False",
}

# Optional dotted path to a callable returning rx.App (e.g. "myapp.reflex:create_app").
# RX_CREATE_APP = "myapp.reflex.create_app"

# Django-led: dotted modules to import so @rx.page / decorators register.
# RX_PAGE_PACKAGES: list[str] = ["myapp.pages"]

# Canned Reflex auth pages (login, register, password reset). See reflex_django.auth.
RX_AUTH = {
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

# Reflex rx.Config overrides (ports, redis_url, frontend_packages, …).
# Preferred home for runtime options. Merged with reflex_mount(..., rx_config={...}) when provided.
RX_CONFIG: dict = {}

# Reflex plugin dotted paths or instances for reflex_mount (optional).
# Example: ["reflex.plugins.RadixThemesPlugin", "reflex.plugins.TailwindV4Plugin"]
RX_PLUGINS: list = []

# Origin for password-reset links when no HTTP request is bound (optional).
# RX_SITE_ORIGIN = "http://localhost:3000"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@localhost"

# When True, :meth:`reflex_django.DjangoUserState.sync_from_django` loads group names.
RX_USER_SNAPSHOT_INCLUDE_GROUPS = False

# When True, :class:`reflex_django.bridge.event.DjangoEventBridge` refreshes
# :class:`~reflex_django.states.AppState` auth snapshot vars on every event.
RX_AUTH_AUTO_SYNC = True

# When True (default), :class:`reflex_django.bridge.event.DjangoEventBridge`
# runs the full ``settings.MIDDLEWARE`` chain on every Reflex event via
# :class:`reflex_django.bridge.event_handler.EventMiddlewareHandler`. Disable to
# restore the legacy lightweight bridge (only session/auth/locale ran).
RX_RUN_MIDDLEWARE_CHAIN: bool = True

# Middleware classes to skip when running the full chain on Reflex events.
# CSRF cannot pass without a token and AsyncStreamingMiddleware is HTTP-only.
RX_EVENT_MIDDLEWARE_SKIP: tuple[str, ...] = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
)

# Event bridge performance (opt-in). "full" preserves legacy behavior on every event.
RX_EVENT_BRIDGE_MODE = "full"  # "full" | "smart" | "none"

# Middleware subset for the "auth_only" bridge tier (tuple, like MIDDLEWARE).
RX_AUTH_ONLY_MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
)

# Populate request.resolver_match on synthetic event requests.
RX_EVENT_RESOLVE_URL = True

# Optional dotted path: callable(handler_state_cls, event) -> "full"|"auth_only"|"none"
# RX_EVENT_BRIDGE_RESOLVER = "myapp.performance.resolve_bridge_tier"

# Django CACHES alias for session/user bridge cache between events (0 TTL disables).
RX_EVENT_CACHE = "default"
RX_EVENT_CACHE_TTL = 60
RX_EVENT_CACHE_KEY_PREFIX = "rx:event:"

# Opt-in bridge timing logs at DEBUG.
RX_EVENT_METRICS = False
# RX_EVENT_METRICS_LOGGER = "myapp.performance"

# "lean" applies smaller WebSocket deltas when mirror settings still match defaults.
RX_PERFORMANCE_PRESET = "default"  # "default" | "lean"

# When True (default), if a middleware short-circuits with a 3xx response,
# the bridge converts it into a Reflex ``rx.redirect(...)`` event so the
# browser navigates to the target. Disable to handle redirects manually.
RX_AUTO_REDIRECT_FROM_MIDDLEWARE: bool = True

# When True, the event payload (handler kwargs) is fed into ``request.POST``
# of the synthetic request. Off by default — Reflex events are RPC-style,
# not form submissions, so most middleware does not look at POST.
RX_EVENT_POST_FROM_PAYLOAD: bool = False

# Individual mirror toggles for the reactive ``DjangoUserState`` vars
# populated from the middleware chain. Disable to save delta size on apps
# that do not bind these in the UI.
RX_MIRROR_MESSAGES: bool = True
RX_MIRROR_CSRF: bool = True
RX_MIRROR_LANGUAGE: bool = True

# When True (default), Django's catch-all view reverse-proxies "/" to the
# Vite dev server in DEBUG mode. Set to False (or env RX_DEV_PROXY=0)
# to serve the compiled SPA directly even in DEBUG.
RX_DEV_PROXY: bool = True

# When True, dev mode matches native Reflex: open the Vite port (default 3000) for
# the SPA; the backend port (default 8000) serves Django + Reflex endpoints only.
# ``manage.py run_reflex`` enables this by default.
RX_SEPARATE_DEV_PORTS: bool = False

# When True (default), Django's catch-all view runs the Reflex SPA's
# ``index.html`` through Django's template engine with
# :class:`~django.template.RequestContext`. This makes ``{{ request.user }}``,
# ``{{ csrf_token }}``, ``{{ messages }}``, ``{{ LANGUAGE_CODE }}`` and any
# ``settings.TEMPLATES[0]["OPTIONS"]["context_processors"]`` keys usable
# directly inside the SPA shell (both in dev and prod). Set to ``False`` to
# serve the file verbatim. Non-HTML responses (JS bundles, CSS, source maps,
# images) are always served verbatim regardless of this setting.
RX_RENDER_SPA_VIA_TEMPLATE_ENGINE: bool = True

# Whether the "Built with Reflex" badge is shown in the SPA. Reflex's
# upstream default is True; reflex-django flips it to False because most
# Django-first apps ship their own branding. To re-enable, set this to True
# in your Django settings (or pass it via
# ``reflex_mount(rx_config={"show_built_with_reflex": True})``).
RX_SHOW_BUILT_WITH_REFLEX: bool = False

# Controls the default ``manage.py run_reflex`` dev loop.
#
# When False (default), ``run_reflex`` spawns the Vite dev server for
# hot-module reload: editing a Reflex page recompiles ``.web`` and Vite
# hot-reloads only the frontend, while the Django/uvicorn backend keeps
# running (it does NOT auto-restart). Re-run the command — or restart the
# backend manually — to pick up backend/state/event-handler edits.
#
# When True, ``run_reflex`` skips Vite entirely, re-exports the SPA on each
# invocation (the equivalent of ``manage.py export_reflex --frontend-only
# --no-zip --stage-to-static-root``), and serves the resulting bundle from
# disk just like ``--env prod`` would — no Node sidecar, no HMR. In that mode
# the ASGI server auto-reloads + re-exports on every ``.py`` change.
#
# To opt into the serve-from-disk build loop, set this to ``True`` (or pass
# ``--from-build`` on the command line, or env ``RX_SERVE_FROM_BUILD=1``).
# Passing ``--with-vite`` forces the Vite-HMR loop regardless of this setting.
RX_SERVE_FROM_BUILD: bool = False

# Whether Django should build the SPA bundle once at startup when none is on disk.
# Prefer pre-building in CI with ``manage.py export_reflex`` instead.
RX_AUTO_EXPORT_ON_START: bool = False

# Additional reserved Reflex path prefixes (advanced; usually not needed).
# Combined with :data:`reflex_django.core.constants.RESERVED_REFLEX_PREFIXES`.
RX_RESERVED_REFLEX_PREFIXES: tuple[str, ...] = ()

# Static files (CSS, JavaScript, images) — served by ASGIStaticFilesHandler in
# DEBUG mode, or from STATIC_ROOT (populated by ``reflex django collectstatic``)
# otherwise. The default path is mirrored in the plugin so the dispatcher
# forwards ``/static/*`` to Django.
STATIC_URL = os.environ.get("RX_STATIC_URL", "/static/")
STATIC_ROOT = os.environ.get(
    "RX_STATIC_ROOT",
    str(Path.cwd() / ".reflex-django" / "staticfiles"),
)

SECRET_KEY = os.environ.get("RX_SECRET_KEY") or secrets.token_urlsafe(50)

# Reflex login/logout sync ``sessionid`` via ``document.cookie`` because WebSocket
# events do not deliver Django ``Set-Cookie`` to the browser. Apps that require
# HttpOnly session cookies should use a dedicated HTTP cookie-sync view instead.
SESSION_COOKIE_HTTPONLY = False

# Session keys copied before ``alogout`` and restored on the new anonymous session
# (e.g. ``self.session["theme"]``). Does not affect ``localStorage`` preferences.
RX_LOGOUT_PRESERVE_SESSION_KEYS: tuple[str, ...] = ("theme",)

DEBUG = os.environ.get("RX_DEBUG", "1") not in {"0", "false", "False"}

ALLOWED_HOSTS = os.environ.get("RX_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django.contrib.staticfiles",
    "reflex_django.django.apps.ReflexDjangoConfig",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "reflex_django.bridge.streaming.AsyncStreamingMiddleware",
]

ROOT_URLCONF = os.environ.get("RX_URLCONF", "reflex_django.django.urls")

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
