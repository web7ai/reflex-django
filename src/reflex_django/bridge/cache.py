"""Django-cache-backed event bridge context cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.cache import caches

_CACHE_SETTINGS_KEY: str | None = None
_CACHE_ALIAS = "default"
_CACHE_TTL = 60
_CACHE_KEY_PREFIX = "rx:event:"


@dataclass(frozen=True)
class CachedEventContext:
    """Pickle-safe snapshot stored between Reflex events."""

    user_id: int | None
    is_authenticated: bool


def _refresh_cache_config() -> None:
    global _CACHE_SETTINGS_KEY, _CACHE_ALIAS, _CACHE_TTL, _CACHE_KEY_PREFIX
    try:
        from django.conf import settings

        settings_key = str(getattr(settings, "SETTINGS_MODULE", "") or "")
        if settings_key == _CACHE_SETTINGS_KEY:
            return
        alias = getattr(settings, "RX_EVENT_CACHE", "default")
        _CACHE_ALIAS = (
            alias.strip() if isinstance(alias, str) and alias.strip() else "default"
        )
        _CACHE_TTL = int(getattr(settings, "RX_EVENT_CACHE_TTL", 60))
        prefix = getattr(settings, "RX_EVENT_CACHE_KEY_PREFIX", "rx:event:")
        _CACHE_KEY_PREFIX = (
            prefix if isinstance(prefix, str) and prefix else "rx:event:"
        )
        _CACHE_SETTINGS_KEY = settings_key
    except Exception:
        _CACHE_ALIAS = "default"
        _CACHE_TTL = 60
        _CACHE_KEY_PREFIX = "rx:event:"
        _CACHE_SETTINGS_KEY = ""


def _cache_alias() -> str:
    _refresh_cache_config()
    return _CACHE_ALIAS


def _cache_ttl() -> int:
    _refresh_cache_config()
    return _CACHE_TTL


def _key_prefix() -> str:
    _refresh_cache_config()
    return _CACHE_KEY_PREFIX


def _cache_key(session_key: str) -> str:
    return f"{_key_prefix()}{session_key}"


def _cache_backend():
    return caches[_cache_alias()]


def get_cached_event_context(session_key: str) -> CachedEventContext | None:
    """Return cached auth snapshot for *session_key*, or ``None``."""
    if not session_key or _cache_ttl() <= 0:
        return None
    raw = _cache_backend().get(_cache_key(session_key))
    if not isinstance(raw, dict):
        return None
    try:
        return CachedEventContext(
            user_id=raw.get("user_id"),
            is_authenticated=bool(raw.get("is_authenticated")),
        )
    except Exception:
        return None


def set_cached_event_context(session_key: str, request: Any) -> None:
    """Store auth snapshot derived from *request*."""
    if not session_key or _cache_ttl() <= 0:
        return
    user = getattr(request, "user", None)
    is_authenticated = bool(getattr(user, "is_authenticated", False))
    user_id = getattr(user, "pk", None) if is_authenticated else None
    if user_id is not None:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            user_id = None
    payload = {
        "user_id": user_id,
        "is_authenticated": is_authenticated,
    }
    _cache_backend().set(_cache_key(session_key), payload, _cache_ttl())


def invalidate_event_cache(session_key: str | None = None) -> None:
    """Drop cached bridge context for *session_key* or the entire cache alias."""
    if _cache_ttl() <= 0:
        return
    backend = _cache_backend()
    if session_key:
        backend.delete(_cache_key(session_key))
    else:
        try:
            backend.clear()
        except Exception:
            pass

    try:
        from reflex_django.signals import event_bridge_cache_invalidated

        event_bridge_cache_invalidated.send(
            sender=invalidate_event_cache,
            session_key=session_key,
        )
    except Exception:
        pass


__all__ = [
    "CachedEventContext",
    "get_cached_event_context",
    "invalidate_event_cache",
    "set_cached_event_context",
]
