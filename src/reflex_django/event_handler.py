"""Run the full Django middleware chain on Reflex Socket.IO events.

Reflex events arrive over Socket.IO and never traverse Django's HTTP request
pipeline, so the ``settings.MIDDLEWARE`` list normally has no effect on them.
:class:`~reflex_django.middleware.DjangoEventBridge` synthesizes a Django
:class:`~django.http.HttpRequest` from each event's ``router_data`` and pipes
it through :class:`EventMiddlewareHandler` — a subclass of
:class:`django.core.handlers.base.BaseHandler` whose only job is to reuse
Django's own ``load_middleware`` plumbing on our synthetic request.

This means **every** entry in ``settings.MIDDLEWARE`` (except the explicit
:data:`DEFAULT_EVENT_MIDDLEWARE_SKIP` set) runs on every Reflex event, in
the same order as a real HTTP request. ``SessionMiddleware``,
``AuthenticationMiddleware``, ``MessageMiddleware``, ``LocaleMiddleware``,
custom middleware — all of them populate the synthetic request before the
event handler runs. The terminal "view" returns an empty 200 response so
the chain has something to thread; middleware that short-circuits with a
redirect or other response is intercepted by the bridge and translated
into Reflex actions (e.g. :func:`reflex.redirect`).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("reflex_django.event_handler")

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


# Middleware classes that should never run for Reflex events. Reflex events
# arrive over Socket.IO and have no CSRF tokens or HTTP-response bodies, so
# ``CsrfViewMiddleware`` would reject every event with 403 and
# ``AsyncStreamingMiddleware`` only adapts streaming HTTP responses.
DEFAULT_EVENT_MIDDLEWARE_SKIP: tuple[str, ...] = (
    "django.middleware.csrf.CsrfViewMiddleware",
    "reflex_django.streaming_middleware.AsyncStreamingMiddleware",
)


def _settings_skip_list() -> tuple[str, ...]:
    """Return the effective skip list (defaults + ``settings`` override)."""
    try:
        from django.conf import settings

        extra = getattr(settings, "REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP", None)
    except Exception:
        extra = None

    if extra is None:
        return DEFAULT_EVENT_MIDDLEWARE_SKIP
    return tuple(str(p) for p in extra if str(p).strip())


class _EmptyOkResponse:
    """Lazy import of :class:`~django.http.HttpResponse` for the terminal view."""

    def __call__(self) -> HttpResponse:
        from django.http import HttpResponse

        return HttpResponse(status=200, content=b"")


_terminal_response = _EmptyOkResponse()


def _filtered_middleware_setting(skip: set[str]) -> list[str]:
    """Return ``settings.MIDDLEWARE`` with entries in *skip* removed."""
    from django.conf import settings

    return [m for m in getattr(settings, "MIDDLEWARE", ()) if m not in skip]


def _build_event_handler_class():
    """Build the :class:`EventMiddlewareHandler` class lazily.

    The class subclasses :class:`django.core.handlers.base.BaseHandler` and is
    only constructed after Django apps are loaded, otherwise importing this
    module top-level would force premature Django setup.
    """
    from django.core.handlers.base import BaseHandler

    class EventMiddlewareHandler(BaseHandler):
        """A :class:`BaseHandler` that exposes the middleware chain for Socket.IO events.

        Behaves like Django's ASGI handler for middleware loading purposes —
        ``load_middleware(is_async=True)`` builds ``_middleware_chain`` from
        ``settings.MIDDLEWARE`` filtered by
        :func:`~reflex_django.event_handler._settings_skip_list`. The terminal
        "view" (``_get_response_async``) returns an empty 200 ``HttpResponse``
        so the chain has a definite endpoint; if any middleware short-circuits
        before reaching the terminal, that response is returned to the
        bridge and translated into a Reflex action.
        """

        skip: tuple[str, ...]

        def __init__(self, skip: tuple[str, ...] | None = None) -> None:
            super().__init__()
            self.skip = skip if skip is not None else _settings_skip_list()

        def load_middleware(self, is_async: bool = False) -> None:
            """Load ``settings.MIDDLEWARE`` minus the configured skip list.

            We temporarily replace ``settings.MIDDLEWARE`` so Django's own
            loader builds the chain we want. Restoring the original value
            in the ``finally`` block keeps the rest of Django's HTTP path
            (admin views, custom views) unaffected.
            """
            from django.conf import settings

            skip_set = set(self.skip)
            original = list(getattr(settings, "MIDDLEWARE", ()))
            filtered = [m for m in original if m not in skip_set]
            try:
                settings.MIDDLEWARE = filtered  # type: ignore[misc]
                super().load_middleware(is_async=is_async)
            finally:
                settings.MIDDLEWARE = original  # type: ignore[misc]

        def _get_response(self, request: HttpRequest) -> HttpResponse:
            return _terminal_response()

        async def _get_response_async(
            self,
            request: HttpRequest,
        ) -> HttpResponse:
            return _terminal_response()

    return EventMiddlewareHandler


# Module-level singletons. Two are kept so async- and sync-style middleware
# chains are both available without re-running ``load_middleware``.
_handler_lock = threading.RLock()
_async_handler: Any | None = None
_sync_handler: Any | None = None
_skip_signature: tuple[str, ...] | None = None


def _reset_singletons() -> None:
    """Drop cached handlers (tests only)."""
    global _async_handler, _sync_handler, _skip_signature
    with _handler_lock:
        _async_handler = None
        _sync_handler = None
        _skip_signature = None


def _get_handler(*, is_async: bool) -> Any:
    """Return a singleton :class:`EventMiddlewareHandler` for the current process.

    Rebuilds the handler if the skip list changes (typically only in tests).
    """
    global _async_handler, _sync_handler, _skip_signature

    skip = _settings_skip_list()
    with _handler_lock:
        if _skip_signature != skip:
            _async_handler = None
            _sync_handler = None
            _skip_signature = skip

        handler = _async_handler if is_async else _sync_handler
        if handler is None:
            handler_cls = _build_event_handler_class()
            handler = handler_cls(skip=skip)
            handler.load_middleware(is_async=is_async)
            if is_async:
                _async_handler = handler
            else:
                _sync_handler = handler
        return handler


async def run_middleware_chain(request: HttpRequest) -> HttpResponse:
    """Run ``settings.MIDDLEWARE`` against ``request`` and return the final response.

    The response is either the empty 200 produced by the terminal "view"
    (meaning every middleware passed the request through unchanged) or
    whatever short-circuit response a middleware returned (e.g. a 302
    redirect from ``LoginRequiredMiddleware``).

    Args:
        request: The synthetic Django request built from the Reflex event.

    Returns:
        The :class:`~django.http.HttpResponse` produced by the chain.
    """
    handler = _get_handler(is_async=True)
    chain = getattr(handler, "_middleware_chain", None)
    if chain is None:
        logger.warning(
            "EventMiddlewareHandler._middleware_chain is unset; "
            "running terminal response."
        )
        return _terminal_response()

    result = chain(request)
    if asyncio.iscoroutine(result):
        result = await result
    return result


__all__ = [
    "DEFAULT_EVENT_MIDDLEWARE_SKIP",
    "_reset_singletons",
    "run_middleware_chain",
]
