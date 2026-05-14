"""Tests for reflex-django i18n activation in :class:`DjangoEventBridge`."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from reflex_django.conf import configure_django

configure_django()

from django.conf import settings  # noqa: E402
from django.http import HttpRequest  # noqa: E402
from django.utils import translation  # noqa: E402
from reflex_django.context import begin_event_request, end_event_request  # noqa: E402
from reflex_django.middleware import DjangoEventBridge  # noqa: E402
from reflex_django.reflex_context import builtin_i18n_context  # noqa: E402


class _StubEvent:
    """Minimal stand-in for reflex_base.event.Event with router_data only."""

    def __init__(self, router_data: dict[str, Any] | None = None) -> None:
        self.router_data = router_data or {}


def _run_in_fresh_context(coro_factory):
    """Run an async function inside a new contextvars.Context.

    Args:
        coro_factory: A zero-arg callable returning the coroutine to run.

    Returns:
        Whatever ``coro_factory()`` returns when awaited.
    """
    import asyncio
    import contextvars

    async def _wrapped():
        return await coro_factory()

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped())


def test_preprocess_sets_language_from_accept_language() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {"accept-language": "de,en;q=0.9"},
            "ip": "",
            "pathname": "/",
        }
    )

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert translation.get_language() == "de"

    _run_in_fresh_context(_go)


def test_preprocess_language_cookie_overrides_accept_language() -> None:
    bridge = DjangoEventBridge()
    cn = settings.LANGUAGE_COOKIE_NAME
    event = _StubEvent(
        router_data={
            "headers": {
                "cookie": f"{cn}=de",
                "accept-language": "en-US,en;q=0.9",
            },
            "ip": "",
            "pathname": "/",
        }
    )

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert translation.get_language() == "de"

    _run_in_fresh_context(_go)


def test_builtin_i18n_context_matches_request() -> None:
    end_event_request()
    req = HttpRequest()
    cast(Any, req).method = "GET"
    cast(Any, req).LANGUAGE_CODE = "de"
    req.META = {}
    begin_event_request(req)
    try:
        translation.activate("de")
        ctx = builtin_i18n_context(req)
        assert ctx["LANGUAGE_CODE"] == "de"
        assert ctx["LANGUAGE_BIDI"] is False
        assert ["en", "English"] in ctx["LANGUAGES"]
        assert ["de", "German"] in ctx["LANGUAGES"]
    finally:
        end_event_request()
        translation.deactivate()
