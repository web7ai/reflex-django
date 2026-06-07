"""ASGI HTTP reverse proxy to a separate Django HTTP upstream (REFLEX_OUTER mode)."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from reflex_django.asgi import ASGIApp, ASGIMessage, ASGIReceive, ASGIScope, ASGISend

logger = logging.getLogger("reflex_django.django_http_proxy")

_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)

_HTTP_CLIENT: Any = None
_HTTP_CLIENT_UPSTREAM: str | None = None


def _forward_request_headers(scope: ASGIScope) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for key, value in scope.get("headers", ()):
        name = key.decode("latin-1") if isinstance(key, bytes) else str(key)
        if name.lower() in _HOP_BY_HOP:
            continue
        val = value.decode("latin-1") if isinstance(value, bytes) else str(value)
        headers.append((name, val))
    return headers


def _query_string(scope: ASGIScope) -> str:
    raw = scope.get("query_string", b"")
    if isinstance(raw, str):
        return raw
    return raw.decode("latin-1")


def _build_path_and_query(scope: ASGIScope) -> str:
    path = scope.get("path", "") or "/"
    qs = _query_string(scope)
    if qs:
        return f"{path}?{qs}"
    return path


async def _read_body(receive: ASGIReceive) -> bytes:
    body = b""
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        body += message.get("body", b"") or b""
        if not message.get("more_body"):
            break
    return body


async def _get_client(upstream_base: str) -> Any:
    global _HTTP_CLIENT, _HTTP_CLIENT_UPSTREAM
    if _HTTP_CLIENT is not None and _HTTP_CLIENT_UPSTREAM == upstream_base:
        return _HTTP_CLIENT

    if _HTTP_CLIENT is not None:
        await _HTTP_CLIENT.aclose()

    try:
        import httpx
    except ImportError as exc:
        msg = (
            "reflex_django.django_http_proxy requires httpx. "
            "Install with pip install httpx."
        )
        raise RuntimeError(msg) from exc

    parts = urlsplit(upstream_base.rstrip("/"))
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    _HTTP_CLIENT = httpx.AsyncClient(
        base_url=base,
        timeout=httpx.Timeout(30.0, connect=5.0),
        follow_redirects=False,
    )
    _HTTP_CLIENT_UPSTREAM = upstream_base
    return _HTTP_CLIENT


async def close_http_proxy_client() -> None:
    global _HTTP_CLIENT, _HTTP_CLIENT_UPSTREAM
    if _HTTP_CLIENT is not None:
        await _HTTP_CLIENT.aclose()
    _HTTP_CLIENT = None
    _HTTP_CLIENT_UPSTREAM = None


async def _send_error(send: ASGISend, status: int, detail: str) -> None:
    body = detail.encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _close_websocket(receive: ASGIReceive, send: ASGISend) -> None:
    try:
        msg = await receive()
        if msg.get("type") != "websocket.connect":
            return
        await send({"type": "websocket.close", "code": 1011})
    except Exception:
        with contextlib.suppress(Exception):
            await send({"type": "websocket.close", "code": 1011})


async def _proxy_http(
    scope: ASGIScope,
    receive: ASGIReceive,
    send: ASGISend,
    *,
    upstream_base: str,
) -> None:
    method = (scope.get("method") or "GET").upper()
    path = _build_path_and_query(scope)
    headers = _forward_request_headers(scope)
    body = b""
    if method not in {"GET", "HEAD"}:
        body = await _read_body(receive)

    try:
        client = await _get_client(upstream_base)
        upstream = await client.request(
            method,
            path,
            headers=headers,
            content=body if body else None,
        )
    except Exception as exc:
        logger.warning("Django HTTP proxy failed for %s %s: %r", method, path, exc)
        await _send_error(
            send,
            502,
            f"reflex-django: Django HTTP upstream unreachable at {upstream_base}: {exc!r}",
        )
        return

    response_headers: list[tuple[bytes, bytes]] = []
    for key, value in upstream.headers.items():
        if key.lower() in _HOP_BY_HOP:
            continue
        response_headers.append((key.encode("latin-1"), value.encode("latin-1")))

    await send(
        {
            "type": "http.response.start",
            "status": upstream.status_code,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": upstream.content})


def make_django_http_proxy(upstream_base: str) -> ASGIApp:
    upstream = upstream_base.rstrip("/")

    async def proxy_app(
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "http":
            await _proxy_http(scope, receive, send, upstream_base=upstream)
            return
        if scope_type == "websocket":
            await _close_websocket(receive, send)
            return

    proxy_app.upstream_base = upstream
    return proxy_app


__all__ = ["close_http_proxy_client", "make_django_http_proxy"]