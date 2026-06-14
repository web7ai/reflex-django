"""Tests for reflex_django.bridge.event.DjangoEventBridge."""

from __future__ import annotations

import contextvars
from typing import Any, cast
from unittest import mock

from reflex_django.setup.conf import configure_django

configure_django()

from django.http import QueryDict  # noqa: E402

from reflex_django.bridge.context import (  # noqa: E402
    current_request,
    current_session,
    current_user,
)
from reflex_django.bridge.event import DjangoEventBridge  # noqa: E402


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

    async def _wrapped():
        return await coro_factory()

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped())


def test_preprocess_binds_request_with_cookies_and_headers() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {
                "cookie": "sessionid=abc; csrftoken=zzz",
                "x-custom": "value",
            },
            "ip": "1.2.3.4",
            "pathname": "/some/route",
        }
    )

    async def _go() -> None:
        result = await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert result is None
        req = current_request()
        assert req is not None
        assert req.COOKIES["sessionid"] == "abc"
        assert req.COOKIES["csrftoken"] == "zzz"
        assert req.META["REMOTE_ADDR"] == "1.2.3.4"
        assert req.META["HTTP_X_CUSTOM"] == "value"
        assert req.path == "/some/route"
        assert req.GET == QueryDict()
        assert req.GET.get("missing") is None

    _run_in_fresh_context(_go)


def test_preprocess_populates_get_from_query_and_pathname() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {},
            "ip": "127.0.0.1",
            "pathname": "/list?page=2",
            "query": {"sort": "asc"},
        }
    )

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        req = current_request()
        assert req is not None
        assert req.path == "/list"
        assert req.GET.get("page") == "2"
        assert req.GET.get("sort") == "asc"

    _run_in_fresh_context(_go)


def test_preprocess_populates_anonymous_user_when_no_session() -> None:
    from django.contrib.auth.models import AnonymousUser

    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={"headers": {}, "ip": "", "pathname": "/"})

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        user = current_user()
        assert isinstance(user, AnonymousUser)
        assert current_session() is not None

    _run_in_fresh_context(_go)


def test_preprocess_handles_missing_router_data() -> None:
    bridge = DjangoEventBridge()

    class _BareEvent:
        pass

    async def _go() -> None:
        result = await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, _BareEvent())
        )
        assert result is None
        req = current_request()
        # Even without router_data, the bridge should still construct a
        # request and populate AnonymousUser.
        assert req is not None
        assert req.COOKIES == {}

    _run_in_fresh_context(_go)


def test_preprocess_handles_malformed_cookie_header() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={"headers": {"cookie": "totally not a cookie"}})

    async def _go() -> None:
        result = await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert result is None
        req = current_request()
        assert req is not None
        # Malformed cookie header should not crash the bridge.
        assert isinstance(req.COOKIES, dict)

    _run_in_fresh_context(_go)


def test_preprocess_does_not_return_state_update() -> None:
    """The bridge must never return a non-None StateUpdate."""
    bridge = DjangoEventBridge()
    event = _StubEvent()

    async def _go() -> None:
        result = await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert result is None

    _run_in_fresh_context(_go)


def test_ac6_preprocess_uses_aget_user() -> None:
    """AC6: authentication reuses Django's aget_user, not a parallel stack."""
    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={"headers": {}, "ip": "", "pathname": "/"})

    async def _go() -> None:
        with mock.patch(
            "django.contrib.auth.aget_user",
            new=mock.AsyncMock(),
        ) as aget:
            from django.contrib.auth.models import AnonymousUser

            aget.return_value = AnonymousUser()
            await bridge.preprocess(
                app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
            )
            aget.assert_awaited_once()
            req = current_request()
            assert req is not None
            assert isinstance(current_user(), AnonymousUser)

    _run_in_fresh_context(_go)


def test_postprocess_clears_current_request() -> None:
    from reflex.state import StateUpdate

    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {"cookie": ""},
            "ip": "",
            "pathname": "/first",
        }
    )

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        req = current_request()
        assert req is not None
        assert req.path == "/first"
        out = await bridge.postprocess(
            app=mock.Mock(),
            state=mock.Mock(),
            event=cast(Any, event),
            update=StateUpdate(),
        )
        assert isinstance(out, StateUpdate)
        assert current_request() is None

    _run_in_fresh_context(_go)


def test_second_preprocess_replaces_request() -> None:
    bridge = DjangoEventBridge()

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(),
            state=mock.Mock(),
            event=cast(
                Any,
                _StubEvent(router_data={"headers": {}, "ip": "", "pathname": "/a"}),
            ),
        )
        first = current_request()
        assert first is not None
        assert first.path == "/a"
        await bridge.preprocess(
            app=mock.Mock(),
            state=mock.Mock(),
            event=cast(
                Any,
                _StubEvent(router_data={"headers": {}, "ip": "", "pathname": "/b"}),
            ),
        )
        second = current_request()
        assert second is not None
        assert second.path == "/b"

    _run_in_fresh_context(_go)
