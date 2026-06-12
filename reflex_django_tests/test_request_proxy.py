"""Tests for :mod:`reflex_django.bridge.request` (module-level request proxy)."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from reflex_django.setup.conf import configure_django

configure_django()

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.http import QueryDict  # noqa: E402

from reflex_django import request  # noqa: E402
from reflex_django.bridge.context import end_event_request  # noqa: E402
from reflex_django.bridge.django_event import DjangoEventBridge  # noqa: E402


class _StubEvent:
    def __init__(self, router_data: dict[str, Any] | None = None) -> None:
        self.router_data = router_data or {}


def _run_in_fresh_context(coro_factory):
    import asyncio

    async def _wrapped():
        return await coro_factory()

    import contextvars

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped())


def test_request_proxy_outside_event_soft_defaults() -> None:
    end_event_request()
    assert isinstance(request.user, AnonymousUser)
    assert request.username == ""
    assert request.is_authenticated is False
    assert request.email == ""
    assert request.session is None
    assert request.GET == QueryDict()
    assert request.headers.get("x-missing") is None
    assert request.path == "/"
    assert not request


def test_request_proxy_after_preprocess() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {
                "cookie": "sessionid=abc",
                "x-custom": "hello",
            },
            "ip": "10.0.0.1",
            "pathname": "/items?page=2",
            "query": {"sort": "name", "page": "3"},
        }
    )

    async def _go() -> None:
        await bridge.preprocess(
            app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
        )
        assert request
        assert isinstance(request.user, AnonymousUser)
        assert request.session is not None
        assert request.path == "/items"
        assert request.GET.get("page") == "3"
        assert request.GET.get("sort") == "name"
        assert request.headers.get("x-custom") == "hello"
        assert request.COOKIES.get("sessionid") == "abc"
        assert request.META["REMOTE_ADDR"] == "10.0.0.1"
        assert request.django_request is not None
        assert request.django_request.path == "/items"

    _run_in_fresh_context(_go)
    end_event_request()


def test_request_get_from_pathname_query_only() -> None:
    from reflex_django.bridge.django_event import _build_request_from_event

    event = _StubEvent(
        router_data={
            "headers": {},
            "pathname": "/search?q=reflex&page=1",
        }
    )
    http = _build_request_from_event(cast(Any, event))
    assert http.path == "/search"
    assert http.GET.get("q") == "reflex"
    assert http.GET.get("page") == "1"


def test_lazy_package_import_request() -> None:
    import importlib

    pkg = importlib.import_module("reflex_django")
    req = pkg.request
    assert req is request
