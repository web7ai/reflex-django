"""ASGI dispatcher tests for django_led routing mode."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from reflex_django.asgi import make_dispatcher
from reflex_django.routing import UrlRoutingMode

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]


class _Recorder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.scopes: list[ASGIScope] = []

    async def __call__(
        self,
        scope: ASGIScope,
        receive: Callable[[], Awaitable[ASGIMessage]],
        send: Callable[[ASGIMessage], Awaitable[None]],
    ) -> None:
        self.scopes.append(scope)


async def _noop_receive() -> ASGIMessage:  # noqa: RUF029
    return {"type": "http.request"}


async def _noop_send(message: ASGIMessage) -> None:  # noqa: RUF029
    return None


async def test_django_led_admin_to_django_spa_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(
        django,
        backend_prefixes=("/api", "/admin"),
        routing_mode=UrlRoutingMode.DJANGO_LED,
    )
    dispatch = transformer(reflex)

    await dispatch({"type": "http", "path": "/admin/"}, _noop_receive, _noop_send)
    await dispatch({"type": "http", "path": "/"}, _noop_receive, _noop_send)
    await dispatch({"type": "http", "path": "/about"}, _noop_receive, _noop_send)

    assert [s["path"] for s in django.scopes] == ["/admin/"]
    assert [s["path"] for s in reflex.scopes] == ["/", "/about"]


async def test_django_led_reserved_paths_always_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(
        django,
        backend_prefixes=("/admin",),
        routing_mode=UrlRoutingMode.DJANGO_LED,
    )
    dispatch = transformer(reflex)

    for path in ["/_event", "/_upload", "/_health", "/ping"]:
        await dispatch({"type": "http", "path": path}, _noop_receive, _noop_send)

    assert django.scopes == []
    assert len(reflex.scopes) == 4


async def test_django_led_websocket_event_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(
        django,
        backend_prefixes=("/admin",),
        routing_mode=UrlRoutingMode.DJANGO_LED,
    )
    dispatch = transformer(reflex)

    await dispatch(
        {"type": "websocket", "path": "/_event/"},
        _noop_receive,
        _noop_send,
    )

    assert reflex.scopes[0]["path"] == "/_event/"
    assert django.scopes == []
