"""Tests for the Vite HMR WebSocket reverse-proxy (single-port dev mode)."""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

import reflex_django.dev.proxy as dev_proxy


class _FakeUpstream:
    """Minimal stand-in for a connected ``websockets`` client."""

    def __init__(self, subprotocol: str | None) -> None:
        self.subprotocol = subprotocol
        self.sent: list[Any] = []
        self.closed = False

    async def send(self, payload: Any) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self) -> "_FakeUpstream":
        return self

    async def __anext__(self) -> Any:
        raise StopAsyncIteration


class _FakeConnect:
    def __init__(self, upstream: _FakeUpstream) -> None:
        self._upstream = upstream

    async def __aenter__(self) -> _FakeUpstream:
        return self._upstream

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _install_fake_transports(
    monkeypatch: pytest.MonkeyPatch,
    upstream: _FakeUpstream,
    connect_calls: list[dict[str, Any]],
) -> None:
    """Inject fake ``httpx`` and ``websockets`` modules for the proxy import."""
    monkeypatch.setitem(sys.modules, "httpx", types.ModuleType("httpx"))

    fake_ws = types.ModuleType("websockets")

    def _connect(url: str, **kwargs: Any) -> _FakeConnect:
        connect_calls.append({"url": url, "kwargs": kwargs})
        return _FakeConnect(upstream)

    fake_ws.connect = _connect  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "websockets", fake_ws)


def test_hmr_proxy_forwards_subprotocol_both_ways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The proxy requests ``vite-hmr`` upstream and echoes it back on accept."""
    monkeypatch.setattr(
        dev_proxy, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    upstream = _FakeUpstream(subprotocol="vite-hmr")
    connect_calls: list[dict[str, Any]] = []
    _install_fake_transports(monkeypatch, upstream, connect_calls)

    scope = {
        "type": "websocket",
        "path": "/",
        "query_string": b"",
        "subprotocols": ["vite-hmr"],
    }
    incoming = [
        {"type": "websocket.connect"},
        {"type": "websocket.disconnect"},
    ]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return incoming.pop(0)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(dev_proxy.proxy_websocket_to_vite(scope, receive, send))

    # Upstream connect requested the browser's subprotocol.
    assert connect_calls
    assert connect_calls[0]["kwargs"].get("subprotocols") == ["vite-hmr"]

    # The accept echoed the negotiated subprotocol back to the browser.
    accept = next(m for m in sent if m["type"] == "websocket.accept")
    assert accept.get("subprotocol") == "vite-hmr"


def test_hmr_proxy_closes_when_no_vite_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no Vite target (prod / opt-out) the socket is closed politely."""
    monkeypatch.setattr(dev_proxy, "_dev_vite_target_or_none", lambda: None)

    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        dev_proxy.proxy_websocket_to_vite(
            {"type": "websocket", "path": "/"}, receive, send
        )
    )

    assert any(m["type"] == "websocket.close" for m in sent)
