"""Opt-in cached fast path for the ``auth_only`` bridge tier.

When ``RX_EVENT_CACHE_FAST_AUTH`` is enabled and a fresh cache entry exists for
the request's ``sessionid``, the bridge skips running the Session/Auth
middleware chain. Instead it:

- attaches a *lazy* session (``SessionStore(session_key)`` performs no DB I/O
  until the session is actually read), and
- resolves ``request.user`` directly from the cached primary key off the event
  loop (one ``aget`` query), skipping the session decode the auth middleware
  would otherwise perform.

The cache (and therefore this fast path) is invalidated on logout via
:func:`reflex_django.bridge.cache.invalidate_event_cache`, but a brief
staleness window (up to ``RX_EVENT_CACHE_TTL`` seconds) is possible, which is
why this remains opt-in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


def fast_auth_enabled() -> bool:
    """Whether the cached auth_only fast path is enabled in settings."""
    try:
        from django.conf import settings

        return bool(getattr(settings, "RX_EVENT_CACHE_FAST_AUTH", False))
    except Exception:
        return False


def _attach_lazy_session(request: HttpRequest, session_key: str) -> None:
    from importlib import import_module

    from django.conf import settings

    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore(session_key)  # type: ignore[attr-defined]


async def _aresolve_cached_user(user_id: int | None, is_authenticated: bool):
    from reflex_django.bridge.context import anonymous_user

    if not is_authenticated or user_id is None:
        return anonymous_user()
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    try:
        return await user_model.objects.aget(pk=user_id)
    except Exception:
        return anonymous_user()


async def try_apply_cached_auth(request: HttpRequest, session_key: str) -> bool:
    """Seed ``request.user``/``request.session`` from cache, skipping middleware.

    Args:
        request: The synthetic request being prepared for the event.
        session_key: The ``sessionid`` cookie value.

    Returns:
        ``True`` when the cache satisfied the request (middleware skipped),
        ``False`` to fall back to the normal middleware chain.
    """
    if not session_key or not fast_auth_enabled():
        return False
    from reflex_django.bridge.cache import get_cached_event_context

    cached = get_cached_event_context(session_key)
    if cached is None:
        return False
    try:
        _attach_lazy_session(request, session_key)
        request.user = await _aresolve_cached_user(  # type: ignore[attr-defined]
            cached.user_id,
            cached.is_authenticated,
        )
    except Exception:
        from reflex_django.core.debug import debug_log_exception

        debug_log_exception("cached auth_only fast path failed; using middleware")
        return False
    return True


__all__ = ["fast_auth_enabled", "try_apply_cached_auth"]
