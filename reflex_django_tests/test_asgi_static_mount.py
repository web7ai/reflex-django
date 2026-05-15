"""Tests for HttpOnlyMount patching of Reflex frontend StaticFiles mounts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import pytest
from reflex_django.asgi import make_dispatcher

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]


class _Recorder:
    def __init__(self) -> None:
        self.scopes: list[ASGIScope] = []

    async def __call__(
        self,
        scope: ASGIScope,
        receive: Callable[[], Awaitable[ASGIMessage]],
        send: Callable[[ASGIMessage], Awaitable[None]],
    ) -> None:
        self.scopes.append(scope)


async def _noop_receive() -> ASGIMessage:  # noqa: RUF029
    return {"type": "http.request", "body": b"", "more_body": False}


async def _noop_send(message: ASGIMessage) -> None:  # noqa: RUF029
    return None


@pytest.fixture
def starlette_with_static_mount(tmp_path: Any) -> Any:
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles

    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    app = Starlette(
        routes=[
            Mount(
                "/",
                app=StaticFiles(directory=str(static_dir), html=True),
                name="frontend",
            ),
        ],
    )
    return app


async def test_websocket_to_static_mount_does_not_assert(
    starlette_with_static_mount: Any,
) -> None:
    django = _Recorder()
    transformer = make_dispatcher(django, backend_prefixes=("/admin",))
    dispatch = transformer(starlette_with_static_mount)

    await dispatch(
        {"type": "websocket", "path": "/", "headers": []},
        _noop_receive,
        _noop_send,
    )


async def test_http_to_static_mount_still_served(
    starlette_with_static_mount: Any,
) -> None:
    django = _Recorder()
    transformer = make_dispatcher(django, backend_prefixes=("/admin",))
    dispatch = transformer(starlette_with_static_mount)

    messages: list[ASGIMessage] = []

    async def capture_send(message: ASGIMessage) -> None:
        messages.append(message)

    await dispatch(
        {
            "type": "http",
            "path": "/",
            "method": "GET",
            "headers": [],
            "query_string": b"",
        },
        _noop_receive,
        capture_send,
    )

    assert any(message.get("type") == "http.response.start" for message in messages)
