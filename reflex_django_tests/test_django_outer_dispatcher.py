"""Pure ASGI tests for :class:`reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`.

The dispatcher must:

- Forward lifespan to Reflex's lifespan context manager.
- Forward reserved Reflex paths (``/_event``, ``/_upload``, …) to the Reflex
  inner ASGI.
- Forward every other ``http`` and ``websocket`` scope to Django.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from reflex_django.django_outer_dispatcher import (
    DEFAULT_RESERVED_REFLEX_PREFIXES,
    DjangoOuterDispatcher,
)

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
        del receive, send
        self.scopes.append(scope)


class _LifespanProbe:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.last_app: Any = None

    @contextlib.asynccontextmanager
    async def __call__(self, app: Any = None):
        self.entered += 1
        self.last_app = app
        try:
            yield
        finally:
            self.exited += 1


async def _send_capture(buf: list[ASGIMessage]):
    async def _send(message: ASGIMessage) -> None:
        buf.append(message)

    return _send


async def test_default_http_routes_to_django() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")

    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=None,
    )

    await dispatcher(
        {"type": "http", "path": "/admin/login/"},
        _stub_receive,
        _stub_send,
    )
    assert django.scopes and django.scopes[0]["path"] == "/admin/login/"
    assert reflex.scopes == []

    await dispatcher(
        {"type": "http", "path": "/"},
        _stub_receive,
        _stub_send,
    )
    assert len(django.scopes) == 2
    assert django.scopes[1]["path"] == "/"


async def test_reserved_paths_route_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")

    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=None,
    )

    for prefix in DEFAULT_RESERVED_REFLEX_PREFIXES:
        await dispatcher(
            {"type": "http", "path": prefix + "/some/sub/path"},
            _stub_receive,
            _stub_send,
        )

    assert len(reflex.scopes) == len(DEFAULT_RESERVED_REFLEX_PREFIXES)
    assert django.scopes == []


async def test_websocket_event_routes_to_reflex() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")

    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=None,
    )
    await dispatcher(
        {"type": "websocket", "path": "/_event"},
        _stub_receive,
        _stub_send,
    )
    assert len(reflex.scopes) == 1
    assert reflex.scopes[0]["type"] == "websocket"


async def test_lifespan_forwarded_to_reflex_lifespan_cm() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    probe = _LifespanProbe()

    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=probe,
    )

    received: list[ASGIMessage] = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]

    async def receive() -> ASGIMessage:
        return received.pop(0)

    sent: list[ASGIMessage] = []

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    await dispatcher({"type": "lifespan"}, receive, send)

    assert probe.entered == 1
    assert probe.exited == 1
    assert {m["type"] for m in sent} == {
        "lifespan.startup.complete",
        "lifespan.shutdown.complete",
    }
    # Reserved-path traffic still routes correctly after lifespan ran.
    assert django.scopes == []


async def test_no_lifespan_cm_still_acks_startup_and_shutdown() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")
    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=None,
    )

    received = [
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ]

    async def receive() -> ASGIMessage:
        return received.pop(0)

    sent: list[ASGIMessage] = []

    async def send(message: ASGIMessage) -> None:
        sent.append(message)

    await dispatcher({"type": "lifespan"}, receive, send)
    assert sent[0]["type"] == "lifespan.startup.complete"
    assert sent[1]["type"] == "lifespan.shutdown.complete"


async def test_extra_reserved_prefixes_added() -> None:
    django = _Recorder("django")
    reflex = _Recorder("reflex")

    dispatcher = DjangoOuterDispatcher(
        django=django,
        reflex=reflex,
        lifespan_cm=None,
        reserved_prefixes=(*DEFAULT_RESERVED_REFLEX_PREFIXES, "/_extra"),
    )
    await dispatcher(
        {"type": "http", "path": "/_extra/payload"},
        _stub_receive,
        _stub_send,
    )
    assert len(reflex.scopes) == 1
    assert django.scopes == []


async def _stub_receive() -> ASGIMessage:
    return {"type": "noop"}


async def _stub_send(message: ASGIMessage) -> None:
    del message
