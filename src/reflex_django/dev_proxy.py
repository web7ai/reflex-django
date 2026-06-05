"""Reverse-proxy frontend requests to the Vite dev server (single-port dev mode).

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER`, Django owns
the outer ASGI app on a single port (default ``8000``). During development,
Reflex still runs Vite on a separate port (default ``3000``) for hot-module
reload. Rather than asking developers to remember two ports, this module
reverse-proxies every non-Reflex, non-Django request (the SPA shell, Vite's
``@vite/client`` HMR WebSocket, ``/_next/static/...`` bundle assets) from
Django back to Vite.

The proxy is used by :class:`reflex_django.views.mount.ReflexMountView` in
``DEBUG=True``. In production, Vite is not running; the same view serves the
compiled SPA from ``STATIC_ROOT`` instead.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger("reflex_django.dev_proxy")

_DEV_PROXY_ENV = "REFLEX_DJANGO_DEV_PROXY"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def dev_uses_separate_ports() -> bool:
    """Return True when the browser should use Vite (:3000) and :8000 is backend-only.

    Matches the native Reflex dev layout: frontend on the Vite port, Django admin/API
    and Reflex Socket.IO on the backend port (proxied from Vite). The Django catch-all
    does **not** reverse-proxy the SPA in this mode.
    """
    env = os.environ.get("REFLEX_DJANGO_SEPARATE_DEV_PORTS")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    try:
        from django.conf import settings

        return bool(getattr(settings, "REFLEX_DJANGO_SEPARATE_DEV_PORTS", False))
    except Exception:
        return False


def dev_proxy_explicitly_enabled() -> bool:
    """Return True only when ``REFLEX_DJANGO_DEV_PROXY`` is explicitly truthy.

    ``manage.py run_reflex`` sets this in its Vite loop so the startup probe
    trusts it (Vite may still be booting). A proxy that is on merely because
    ``DEBUG=True`` is *not* "explicit" and remains subject to the probe.
    """
    return str(os.environ.get(_DEV_PROXY_ENV, "")).strip().lower() in _TRUTHY


if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


# Headers that must not be forwarded verbatim (hop-by-hop or recomputed by httpx).
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


def _resolve_frontend_port_from_config() -> int | None:
    """Return the Reflex frontend port from env, settings, mount registry, or ``rx.Config``."""
    env_port = os.environ.get("REFLEX_DJANGO_FRONTEND_PORT")
    if env_port and env_port.isdigit():
        return int(env_port)
    try:
        from django.conf import settings

        setting_port = getattr(settings, "REFLEX_DJANGO_FRONTEND_PORT", None)
        if isinstance(setting_port, int) and setting_port > 0:
            return setting_port
    except Exception:
        pass
    try:
        from reflex_django.mount_config import (
            ensure_mount_config_loaded,
            get_merged_mount_rx_config,
        )

        ensure_mount_config_loaded()
        mount_port = get_merged_mount_rx_config().rx_config.get("frontend_port")
        if isinstance(mount_port, int) and mount_port > 0:
            return mount_port
    except Exception:
        pass
    try:
        from reflex_base.config import get_config

        cfg = get_config()
        port = getattr(cfg, "frontend_port", None)
        if isinstance(port, int) and port > 0:
            return port
    except Exception:
        pass
    return None


def _dev_vite_target_or_none() -> str | None:
    """Return ``"http://127.0.0.1:<port>"`` when a Vite dev server should be proxied.

    Returns ``None`` outside dev mode (e.g. production, or when the user has
    set ``REFLEX_DJANGO_DEV_PROXY=0`` to opt out).
    """
    try:
        from django.conf import settings
    except Exception:
        return None

    if not settings.configured:
        return None
    if not getattr(settings, "DEBUG", False):
        return None
    if str(os.environ.get("REFLEX_DJANGO_DEV_PROXY", "")).strip().lower() in {
        "0",
        "false",
        "no",
    }:
        return None
    if not getattr(settings, "REFLEX_DJANGO_DEV_PROXY", True):
        return None
    if dev_uses_separate_ports():
        return None

    port = _resolve_frontend_port_from_config()
    if port is None:
        return None
    host = os.environ.get("REFLEX_DJANGO_FRONTEND_HOST", "127.0.0.1")
    return f"http://{host}:{port}"


def _forward_headers(headers: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for key, value in headers.items():
        if key.lower() in _HOP_BY_HOP:
            continue
        out.append((key, value))
    return out


async def reverse_proxy_to_vite(
    request: HttpRequest,
    target: str,
) -> HttpResponse:
    """Stream a HTTP request through to Vite and return the response.

    Args:
        request: The Django ``HttpRequest`` being handled.
        target: Base URL such as ``"http://127.0.0.1:3000"``.

    Returns:
        A Django :class:`~django.http.HttpResponse` (or
        :class:`~django.http.StreamingHttpResponse` for large payloads) whose
        body is the response from Vite.
    """
    from django.http import HttpResponse, StreamingHttpResponse

    try:
        import httpx
    except ImportError:
        msg = (
            "reflex_django.dev_proxy requires httpx for the dev Vite reverse-proxy. "
            "Install with `pip install httpx` or set REFLEX_DJANGO_DEV_PROXY=0 and "
            "open Vite directly on its own port."
        )
        return HttpResponse(msg, status=500, content_type="text/plain")

    parts = urlsplit(target)
    base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    full_path = request.get_full_path()

    method = request.method or "GET"
    headers = _forward_headers(request.headers)
    body = request.body if method.upper() not in {"GET", "HEAD"} else None

    try:
        async with httpx.AsyncClient(
            base_url=base,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=False,
        ) as client:
            upstream = await client.request(
                method,
                full_path,
                headers=headers,
                content=body,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vite dev proxy failed for %s: %r", full_path, exc)
        return HttpResponse(
            f"reflex-django dev proxy could not reach Vite at {target}: {exc!r}",
            status=502,
            content_type="text/plain",
        )

    response: HttpResponse | StreamingHttpResponse
    upstream_content_type = upstream.headers.get("content-type", "").lower()
    is_html = upstream_content_type.split(";", 1)[0].strip() == "text/html"
    is_chunked = upstream.headers.get("transfer-encoding", "").lower() == "chunked"

    # HTML must always be returned as a buffered :class:`HttpResponse` (never
    # a streaming body) so :mod:`reflex_django.spa_template` can pipe it
    # through Django's template engine — the SPA shell needs to render
    # ``{{ request.user }}``, ``{% csrf_token %}``, ``{{ messages }}``, etc.
    # Non-HTML responses (JS bundles, CSS, source maps, images) keep their
    # original streaming behaviour to avoid buffering large assets.
    if is_html or not is_chunked:
        response = HttpResponse(
            upstream.content,
            status=upstream.status_code,
        )
    else:
        response = StreamingHttpResponse(
            (chunk async for chunk in upstream.aiter_bytes()),
            status=upstream.status_code,
        )

    for key, value in upstream.headers.items():
        if key.lower() in _HOP_BY_HOP:
            continue
        response[key] = value
    return response


async def proxy_websocket_to_vite(scope: Any, receive: Any, send: Any) -> None:
    """Forward a Django/ASGI WebSocket scope to the Vite HMR endpoint.

    Vite uses a WebSocket on the same origin for hot-module reload. The
    Django outer dispatcher does not directly hand WebSocket scopes to
    Django views (Django's view layer is HTTP-only), so this is wired
    separately by :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`
    via a higher-level dev proxy hook (set when ``DEBUG``).
    """
    target = _dev_vite_target_or_none()
    if target is None:
        await send({"type": "websocket.close", "code": 1011})
        return

    try:
        import httpx
        import websockets  # type: ignore[import-not-found]
    except ImportError:
        await send({"type": "websocket.close", "code": 1011})
        return

    del httpx  # unused but ensures httpx is installed for HTTP side too

    path = scope.get("path", "/")
    query = scope.get("query_string", b"").decode()
    target_url = (
        f"ws://{target.removeprefix('http://').removeprefix('https://')}"
        f"{path}"
        f"{'?' + query if query else ''}"
    )

    # Vite's HMR client opens the WebSocket with the ``vite-hmr`` subprotocol
    # (React Router / Vite also use ``vite-ping``). The handshake fails unless
    # we (a) request the same subprotocol(s) when connecting to Vite upstream
    # and (b) echo the negotiated subprotocol back to the browser on accept.
    # Without this the proxied socket connects but Vite never treats it as an
    # HMR channel, so edits compile but the browser is never told to reload.
    requested_subprotocols = [
        str(p) for p in scope.get("subprotocols", []) if p
    ]
    connect_kwargs: dict[str, Any] = {}
    if requested_subprotocols:
        connect_kwargs["subprotocols"] = requested_subprotocols

    msg = await receive()
    if msg["type"] != "websocket.connect":
        return

    try:
        async with websockets.connect(  # type: ignore[attr-defined]
            target_url, **connect_kwargs
        ) as upstream:
            negotiated = getattr(upstream, "subprotocol", None)
            accept_msg: dict[str, Any] = {"type": "websocket.accept"}
            if negotiated:
                accept_msg["subprotocol"] = negotiated
            elif requested_subprotocols:
                accept_msg["subprotocol"] = requested_subprotocols[0]
            await send(accept_msg)

            async def from_browser() -> None:
                while True:
                    event = await receive()
                    if event["type"] == "websocket.disconnect":
                        await upstream.close()
                        return
                    payload = event.get("text") or event.get("bytes")
                    if payload is not None:
                        await upstream.send(payload)

            async def from_upstream() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await send({"type": "websocket.send", "bytes": message})
                    else:
                        await send({"type": "websocket.send", "text": message})

            await asyncio.gather(from_browser(), from_upstream())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vite HMR proxy failed: %r", exc)
        await send({"type": "websocket.close", "code": 1011})


__all__ = [
    "_dev_vite_target_or_none",
    "_resolve_frontend_port_from_config",
    "dev_proxy_explicitly_enabled",
    "dev_uses_separate_ports",
    "proxy_websocket_to_vite",
    "reverse_proxy_to_vite",
]
