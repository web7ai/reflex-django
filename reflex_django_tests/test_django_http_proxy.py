"""Tests for the Django HTTP reverse proxy used in REFLEX_OUTER mode."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from unittest import mock

import pytest
from reflex_django.asgi import make_dispatcher
from reflex_django.django_http_proxy import close_http_proxy_client, make_django_http_proxy
from reflex_django.routing import UrlRoutingMode

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


async def _noop_receive() -> ASGIMessage:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _make_send() -> tuple[list[ASGIMessage], Callable[[ASGIMessage], Awaitable[None]]]:
    messages: list[ASGIMessage] = []

    async def send(message: ASGIMessage) -> None:
        messages.append(message)

    return messages, send


@pytest.fixture(autouse=True)
async def _close_client() -> None:
    yield
    await close_http_proxy_client()


async def test_proxy_forwards_admin_request() -> None:
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.content = b"<html>admin</html>"

    mock_client = mock.AsyncMock()
    mock_client.request = mock.AsyncMock(return_value=mock_response)

    with mock.patch(
        "reflex_django.django_http_proxy._get_client",
        mock.AsyncMock(return_value=mock_client),
    ):
        proxy = make_django_http_proxy("http://127.0.0.1:8001")
        messages, send = await _make_send()
        await proxy(
            {
                "type": "http",
                "method": "GET",
                "path": "/admin/login/",
                "query_string": b"",
                "headers": [(b"cookie", b"sessionid=abc")],
            },
            _noop_receive,
            send,
        )

    mock_client.request.assert_awaited_once()
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["headers"] == [("cookie", "sessionid=abc")]
    assert messages[0]["status"] == 200
    assert messages[1]["body"] == b"<html>admin</html>"


async def test_reflex_outer_dispatcher_sends_event_to_reflex_not_proxy() -> None:
    django = _Recorder()
    reflex = _Recorder()
    transformer = make_dispatcher(
        django,
        backend_prefixes=("/admin",),
        routing_mode=UrlRoutingMode.REFLEX_OUTER,
    )
    dispatch = transformer(reflex)

    _, send = await _make_send()
    await dispatch({"type": "http", "path": "/_event"}, _noop_receive, send)
    await dispatch({"type": "http", "path": "/admin/"}, _noop_receive, send)

    assert [s["path"] for s in reflex.scopes] == ["/_event"]
    assert [s["path"] for s in django.scopes] == ["/admin/"]
