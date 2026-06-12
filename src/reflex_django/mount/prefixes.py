"""Shared path prefix resolution for the plugin, ASGI dispatcher, and ``reflex_mount``."""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any


def _resolve_prefix(
    override: str | None,
    *,
    registry_value: str | None,
    env_key: str,
    default: str,
) -> str:
    """Resolve a path prefix: explicit override → mount registry → env → default."""
    for candidate in (override, registry_value):
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    env_val = os.environ.get(env_key, "").strip()
    if env_val:
        return env_val
    return default


def _normalize_path_prefix(prefix: str) -> str:
    """Normalize to ``/segment`` without a trailing slash (empty string allowed)."""
    prefix = prefix.strip()
    if not prefix:
        return ""
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if len(prefix) > 1 and prefix.endswith("/"):
        prefix = prefix.rstrip("/")
    return prefix


@dataclasses.dataclass(frozen=True)
class DjangoPrefixConfig:
    """Resolved Django-led path prefixes."""

    mount_prefix: str
    django_prefix: tuple[str, ...]

    def backend_prefixes_for_asgi(self) -> tuple[str, ...]:
        """Prefixes forwarded to Django by the ASGI dispatcher."""
        parts: list[str] = list(self.django_prefix)
        parts.extend(self._static_prefixes())
        return tuple(dict.fromkeys(_normalize_path_prefix(p) for p in parts if p))

    def reserved_paths_for_catchall(self) -> tuple[str, ...]:
        """Bare paths excluded from the Reflex SPA catch-all regex."""
        paths = [_normalize_path_prefix(p) for p in self.django_prefix]
        static = _static_url_prefix()
        if static:
            paths.append(static)
        try:
            from reflex_django.dev.proxy import dev_uses_separate_ports

            if dev_uses_separate_ports():
                # Two-port dev: ``/`` is backend-owned (project root view), not SPA.
                paths.append("/")
        except Exception:
            pass
        return tuple(dict.fromkeys(p for p in paths if p))

    @staticmethod
    def _static_prefixes() -> tuple[str, ...]:
        try:
            from django.conf import settings
        except Exception:
            return ()
        if "django.contrib.staticfiles" not in getattr(settings, "INSTALLED_APPS", ()):
            return ()
        url = getattr(settings, "STATIC_URL", None)
        if not isinstance(url, str) or not url or "://" in url:
            return ()
        return (_normalize_path_prefix(url),)


def _static_url_prefix() -> str:
    prefixes = DjangoPrefixConfig._static_prefixes()
    return prefixes[0] if prefixes else ""


def _coerce_django_prefix(
    override: str | tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if override is None:
        return None
    if isinstance(override, str):
        return (override,) if override.strip() else ()
    return tuple(str(p) for p in override if str(p).strip())


def _resolve_django_prefix(
    override: str | tuple[str, ...] | None,
    *,
    registry_value: tuple[str, ...] | None,
) -> tuple[str, ...]:
    coerced = _coerce_django_prefix(override)
    if coerced is not None:
        return coerced
    if registry_value is not None:
        return registry_value
    env_raw = os.environ.get("REFLEX_DJANGO_DJANGO_PREFIX", "").strip()
    if env_raw:
        if env_raw.startswith("["):
            try:
                parsed = json.loads(env_raw)
                if isinstance(parsed, list):
                    return tuple(str(p) for p in parsed if str(p).strip())
            except json.JSONDecodeError:
                pass
        return tuple(p.strip() for p in env_raw.split(",") if p.strip())
    return ()


def _mount_registry() -> Any:
    from reflex_django.mount.config import ensure_mount_config_loaded, get_merged_mount_rx_config

    ensure_mount_config_loaded()
    return get_merged_mount_rx_config()


def resolve_prefixes(
    *,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
) -> DjangoPrefixConfig:
    """Resolve path prefixes for django_led routing.

    Prefer :func:`reflex_django.django.urls.reflex_mount` in ``urls.py`` with ``django_prefix``
    listing every Django-owned path (``/admin``, ``/api``, webhooks, …).

    Returns:
        A frozen :class:`DjangoPrefixConfig`.
    """
    mount = _mount_registry()
    return DjangoPrefixConfig(
        mount_prefix=_normalize_path_prefix(
            _resolve_prefix(
                mount_prefix,
                registry_value=mount.mount_prefix,
                env_key="REFLEX_DJANGO_MOUNT_PREFIX",
                default="/",
            )
        )
        or "/",
        django_prefix=_resolve_django_prefix(
            django_prefix,
            registry_value=mount.django_prefix,
        ),
    )


def export_prefix_env(config: DjangoPrefixConfig) -> None:
    """Sync resolved prefixes to the environment for ASGI workers."""
    os.environ.setdefault(
        "REFLEX_DJANGO_MOUNT_PREFIX",
        config.mount_prefix or "/",
    )
    if config.django_prefix:
        os.environ.setdefault(
            "REFLEX_DJANGO_DJANGO_PREFIX",
            json.dumps(list(config.django_prefix)),
        )


def export_rx_port_env() -> None:
    """Sync ``frontend_port`` / ``backend_port`` from ``reflex_mount()`` to the env."""
    try:
        from reflex_django.mount.config import (
            ensure_mount_config_loaded,
            get_merged_mount_rx_config,
        )

        ensure_mount_config_loaded()
        rx_config = get_merged_mount_rx_config().rx_config
    except Exception:
        return

    frontend_port = rx_config.get("frontend_port")
    backend_port = rx_config.get("backend_port")
    if isinstance(frontend_port, int) and frontend_port > 0:
        os.environ.setdefault("REFLEX_DJANGO_FRONTEND_PORT", str(frontend_port))
    if isinstance(backend_port, int) and backend_port > 0:
        os.environ.setdefault("REFLEX_DJANGO_BACKEND_PORT", str(backend_port))
