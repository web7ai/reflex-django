"""Pure ASGI tests for reflex_django.asgi.make_dispatcher.

The dispatcher must route by path prefix while:
- Forwarding lifespan events to the inner Reflex app unconditionally.
- Forwarding Socket.IO (``/_event``) and other Reflex internals away from
  Django.
- Rejecting backend prefixes that collide with Reflex's reserved endpoints.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import pytest
from reflex_django.asgi import RESERVED_REFLEX_PREFIXES, make_dispatcher

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]


class _Recorder:
    """ASGI callable that records every scope it sees."""

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
    return {"type": "lifespan.startup"}


async def _noop_send(message: ASGIMessage) -> None:  # noqa: RUF029
    return None


async def test_routes_to_django_under_backend_prefix() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api", "/admin"))
    dispatch = transformer(reflex)

    await dispatch({"type": "http", "path": "/api/hello"}, _noop_receive, _noop_send)
    await dispatch({"type": "http", "path": "/admin/login/"}, _noop_receive, _noop_send)

    assert len(django.scopes) == 2
    assert django.scopes[0]["path"] == "/api/hello"
    assert django.scopes[1]["path"] == "/admin/login/"
    assert reflex.scopes == []


async def test_routes_to_reflex_for_socketio_and_internals() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api",))
    dispatch = transformer(reflex)

    for path in [
        "/",
        "/_event",
        "/_event/",
        "/_upload",
        "/_health",
        "/ping",
        "/some/frontend/route",
    ]:
        await dispatch({"type": "http", "path": path}, _noop_receive, _noop_send)

    assert len(reflex.scopes) == 7
    assert django.scopes == []


async def test_routes_websocket_to_reflex_unless_under_django_prefix() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api",))
    dispatch = transformer(reflex)

    await dispatch({"type": "websocket", "path": "/_event/"}, _noop_receive, _noop_send)
    await dispatch(
        {"type": "websocket", "path": "/api/stream"}, _noop_receive, _noop_send
    )

    assert [s["path"] for s in reflex.scopes] == ["/_event/"]
    assert [s["path"] for s in django.scopes] == ["/api/stream"]


async def test_lifespan_always_goes_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api",))
    dispatch = transformer(reflex)

    await dispatch({"type": "lifespan"}, _noop_receive, _noop_send)

    assert [s["type"] for s in reflex.scopes] == ["lifespan"]
    assert django.scopes == []


async def test_http_reserved_subpath_under_backend_prefix_goes_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api",))
    dispatch = transformer(reflex)

    await dispatch(
        {"type": "http", "path": "/api/_event"},
        _noop_receive,
        _noop_send,
    )
    await dispatch(
        {"type": "http", "path": "/api/_upload"},
        _noop_receive,
        _noop_send,
    )

    assert django.scopes == []
    assert [s["path"] for s in reflex.scopes] == ["/api/_event", "/api/_upload"]


async def test_exact_prefix_match_routes_to_django() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    transformer = make_dispatcher(django, backend_prefixes=("/api",))
    dispatch = transformer(reflex)

    await dispatch({"type": "http", "path": "/api"}, _noop_receive, _noop_send)
    await dispatch({"type": "http", "path": "/apirent"}, _noop_receive, _noop_send)

    assert [s["path"] for s in django.scopes] == ["/api"]
    assert [s["path"] for s in reflex.scopes] == ["/apirent"]


def test_make_dispatcher_normalizes_prefixes() -> None:
    django = _Recorder("django")
    transformer = make_dispatcher(django, backend_prefixes=("api/", "/admin/"))

    assert transformer.backend_prefixes == ("/api", "/admin")  # pyright: ignore[reportFunctionMemberAccess]


def test_make_dispatcher_rejects_empty_prefix_list() -> None:
    with pytest.raises(ValueError, match="at least one prefix"):
        make_dispatcher(_Recorder("django"), backend_prefixes=())


def test_make_dispatcher_rejects_root_prefix() -> None:
    with pytest.raises(ValueError, match="cannot be '/'"):
        make_dispatcher(_Recorder("django"), backend_prefixes=("/",))


def test_make_dispatcher_rejects_empty_string_prefix() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        make_dispatcher(_Recorder("django"), backend_prefixes=("",))


@pytest.mark.parametrize("reserved", RESERVED_REFLEX_PREFIXES)
def test_make_dispatcher_rejects_reserved_prefixes(reserved: str) -> None:
    with pytest.raises(ValueError, match="reserved endpoint"):
        make_dispatcher(_Recorder("django"), backend_prefixes=(reserved,))


async def test_reflex_outer_reserved_paths_win_over_admin_prefix() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    from reflex_django.routing import UrlRoutingMode

    transformer = make_dispatcher(
        django,
        backend_prefixes=("/admin",),
        routing_mode=UrlRoutingMode.REFLEX_OUTER,
    )
    dispatch = transformer(reflex)

    await dispatch({"type": "http", "path": "/_event"}, _noop_receive, _noop_send)
    await dispatch({"type": "http", "path": "/admin/"}, _noop_receive, _noop_send)

    assert [s["path"] for s in reflex.scopes] == ["/_event"]
    assert [s["path"] for s in django.scopes] == ["/admin/"]


def test_make_dispatcher_rejects_subpath_of_reserved_prefix() -> None:
    with pytest.raises(ValueError, match="reserved endpoint"):
        make_dispatcher(
            _Recorder("django"),
            backend_prefixes=("/_event/extra",),
        )
