"""Environment and settings flag parsing helpers."""

from __future__ import annotations

import os


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


def resolve_rxdjango_proxy_server(*, required: bool = False) -> str:
    """Return the externally managed Django HTTP server base URL for dev proxy."""
    from reflex_django.mount.integration_config import proxy_server_url

    value = proxy_server_url()
    if value:
        return value

    if required:
        from reflex_django.setup.errors import ConfigurationError

        raise ConfigurationError(
            "RX_PROXY_SERVER is not set.\n"
            "When Django runs on a separate HTTP server, start it first, for example:\n"
            "    python manage.py runserver\n"
            "Then set in rxconfig.py:\n"
            '    ReflexDjangoPlugin(config={"embed": {"enabled": False}, '
            '"proxy": {"server": "http://127.0.0.1:8000"}})\n'
            "Or set RX_PROXY_SERVER in settings.py.\n"
            "Leave embed enabled when Django is mounted in the Reflex backend (default)."
        )
    return ""


__all__ = [
    "resolve_rxdjango_proxy_server",
    "setting_or_env_bool",
    "truthy_env",
    "truthy_env_or_none",
]
