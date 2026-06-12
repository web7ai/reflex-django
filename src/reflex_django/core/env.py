"""Environment and settings flag parsing helpers."""

from __future__ import annotations

import os
import warnings


def truthy_env(
    name: str,
    *,
    settings_attr: str | None = None,
    default: bool | None = None,
) -> bool:
    """Return whether an env var or Django setting is truthy."""
    raw = os.environ.get(name)
    if raw is not None:
        return str(raw).strip().lower() not in {"0", "false", "no"}

    if settings_attr is not None:
        try:
            from django.conf import settings

            if settings.configured and hasattr(settings, settings_attr):
                return bool(getattr(settings, settings_attr))
        except Exception:
            pass

    if default is not None:
        return default
    return False


def truthy_env_or_none(name: str) -> bool | None:
    """Return parsed env bool, or None when the variable is unset."""
    raw = os.environ.get(name)
    if raw is None:
        return None
    return str(raw).strip().lower() not in {"0", "false", "no"}


def setting_or_env_bool(
    env_name: str,
    settings_attr: str,
    *,
    default: bool = False,
) -> bool:
    """Resolve a boolean from env first, then Django settings."""
    env_val = truthy_env_or_none(env_name)
    if env_val is not None:
        return env_val
    try:
        from django.conf import settings

        return bool(getattr(settings, settings_attr, default))
    except Exception:
        return default


_PROXY_SERVER_ENV = "RXDJANGO_PROXY_SERVER"
_PROXY_SERVER_SETTING = "RXDJANGO_PROXY_SERVER"
_DEPRECATED_HTTP_UPSTREAM_ENV = "REFLEX_DJANGO_HTTP_UPSTREAM"
_DEPRECATED_HTTP_UPSTREAM_SETTING = "REFLEX_DJANGO_HTTP_UPSTREAM"


def resolve_rxdjango_proxy_server(*, required: bool = False) -> str:
    """Return the externally managed Django HTTP server base URL for dev proxy."""
    env_value = os.environ.get(_PROXY_SERVER_ENV, "").strip()
    if env_value:
        return env_value.rstrip("/")

    try:
        from django.conf import settings

        if settings.configured:
            settings_value = str(
                getattr(settings, _PROXY_SERVER_SETTING, "") or ""
            ).strip()
            if settings_value:
                return settings_value.rstrip("/")
    except Exception:
        pass

    deprecated_env = os.environ.get(_DEPRECATED_HTTP_UPSTREAM_ENV, "").strip()
    if deprecated_env:
        warnings.warn(
            f"{_DEPRECATED_HTTP_UPSTREAM_ENV} is deprecated; "
            f"use {_PROXY_SERVER_ENV} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return deprecated_env.rstrip("/")

    try:
        from django.conf import settings

        if settings.configured:
            deprecated_settings = str(
                getattr(settings, _DEPRECATED_HTTP_UPSTREAM_SETTING, "") or ""
            ).strip()
            if deprecated_settings:
                warnings.warn(
                    f"{_DEPRECATED_HTTP_UPSTREAM_SETTING} is deprecated; "
                    f"use {_PROXY_SERVER_SETTING} instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return deprecated_settings.rstrip("/")
    except Exception:
        pass

    if required:
        from reflex_django.setup.errors import ConfigurationError

        raise ConfigurationError(
            "RXDJANGO_PROXY_SERVER is not set.\n"
            "When Django runs on a separate HTTP server, start it first, for example:\n"
            "    python manage.py runserver\n"
            "Then set in settings.py:\n"
            '    RXDJANGO_PROXY_SERVER = "http://127.0.0.1:8000"\n'
            "Or export RXDJANGO_PROXY_SERVER=http://127.0.0.1:8000.\n"
            "Leave it unset when Django is mounted in the Reflex backend (default)."
        )
    return ""


__all__ = [
    "resolve_rxdjango_proxy_server",
    "setting_or_env_bool",
    "truthy_env",
    "truthy_env_or_none",
]