"""ASGI dispatcher that makes Django the outer application on a single port.

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER` mode, the
ASGI process boots from
:func:`reflex_django.asgi_entry.application`, which composes:

1. Django's ASGI application (with optional staticfiles wrapping) at the
   default ``/`` — admin, custom URLs, static files, and the SPA catch-all
   view all served by Django.
2. Reflex's inner Starlette (``app._api``) at a small set of reserved paths
   (``/_event``, ``/_upload``, ``/_health``, ``/ping`` …) — Socket.IO,
   upload, and health endpoints.
3. ASGI lifespan forwarded to Reflex's
   :meth:`reflex.app.App._run_lifespan_tasks` so the event processor and
   any user-registered lifespan tasks start/stop with the server.

This is the inverse of the legacy :func:`reflex_django.asgi.make_dispatcher`,
which mounted Django inside Reflex. Django is now "the server"; Reflex is a
sub-application carried by it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

logger = logging.getLogger("reflex_django.django_outer_dispatcher")

from reflex_django._frontend_runner import BUILD_ID_PATH
from reflex_django.core.constants import RESERVED_REFLEX_PREFIXES

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


# Backward-compatible alias for docs and settings references.
DEFAULT_RESERVED_REFLEX_PREFIXES: tuple[str, ...] = RESERVED_REFLEX_PREFIXES


def _path_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


class DjangoOuterDispatcher:
    """ASGI app that routes lifespan + reserved paths to Reflex, all else to Django.

    Attributes:
        django: Django's ASGI callable (typically ``get_asgi_application()``
            optionally wrapped in :class:`~django.contrib.staticfiles.handlers.ASGIStaticFilesHandler`).
        reflex: Reflex's inner ASGI callable (``app._api`` wrapped with
            ``app._context_middleware`` so per-request Reflex contexts are bound).
        reserved_prefixes: Path prefixes that always forward to Reflex.
        lifespan_cm: Reflex's lifespan context manager
            (``app._run_lifespan_tasks``), an
            :func:`contextlib.asynccontextmanager`-decorated async generator.
    """

    def __init__(
        self,
        *,
        django: ASGIApp,
        reflex: ASGIApp,
        lifespan_cm: Callable[..., contextlib.AbstractAsyncContextManager[None]] | None,
        reserved_prefixes: tuple[str, ...] = DEFAULT_RESERVED_REFLEX_PREFIXES,
    ) -> None:
        self.django = django
        self.reflex = reflex
        self.lifespan_cm = lifespan_cm
        self.reserved_prefixes = tuple(
            self._normalize(p) for p in reserved_prefixes if p
        )

    @staticmethod
    def _normalize(prefix: str) -> str:
        if not prefix:
            return prefix
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        if len(prefix) > 1 and prefix.endswith("/"):
            prefix = prefix.rstrip("/")
        return prefix

    def _is_reserved(self, path: str) -> bool:
        return any(_path_matches(path, p) for p in self.reserved_prefixes)

    @staticmethod
    async def _serve_compile_dev_build_id(send: ASGISend) -> None:
        """Return a token that changes when the on-disk SPA bundle is rebuilt."""
        from reflex_django._frontend_runner import build_id_for_disk_bundle

        body = build_id_for_disk_bundle().encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope_type not in ("http", "websocket"):
            return

        path = scope.get("path", "") or "/"
        if scope_type == "http" and path == BUILD_ID_PATH:
            await self._serve_compile_dev_build_id(send)
            return

        if self._is_reserved(path):
            await self.reflex(scope, receive, send)
            return

        # Django's ASGI handler only understands HTTP scopes. WebSocket scopes
        # on non-reserved paths are typically Vite's HMR channel during dev
        # (or a Channels app, if the user has wired one). Route WebSockets to
        # the Vite dev proxy when available; otherwise close cleanly so
        # Django's handler does not raise "Django can only handle ASGI/HTTP
        # connections, not websocket".
        if scope_type == "websocket":
            await self._handle_websocket(scope, receive, send)
            return

        await self.django(scope, receive, send)

    async def _handle_websocket(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Forward a WebSocket scope to Vite (dev) or close it gracefully."""
        try:
            from reflex_django.dev_proxy import (
                _dev_vite_target_or_none,
                proxy_websocket_to_vite,
            )
        except Exception:  # noqa: BLE001
            await self._close_websocket(receive, send)
            return

        target = _dev_vite_target_or_none()
        if target is None:
            await self._close_websocket(receive, send)
            return

        try:
            await proxy_websocket_to_vite(scope, receive, send)
        except Exception:  # noqa: BLE001
            logger.exception("Vite HMR WebSocket proxy failed for %s", scope.get("path"))
            await self._close_websocket(receive, send)

    @staticmethod
    async def _close_websocket(receive: ASGIReceive, send: ASGISend) -> None:
        """Politely close an incoming WebSocket connection (1011 = server error)."""
        try:
            msg = await receive()
            if msg.get("type") != "websocket.connect":
                return
            await send({"type": "websocket.close", "code": 1011})
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                await send({"type": "websocket.close", "code": 1011})

    async def _handle_lifespan(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        """Implement the ASGI lifespan protocol against Reflex's lifespan manager.

        Django's ASGI handler ignores lifespan; only Reflex needs it (event
        processor, background tasks, prerender). If no manager is provided we
        respond with ``startup.complete`` / ``shutdown.complete`` so the server
        does not hang.
        """
        del scope
        cm: contextlib.AbstractAsyncContextManager[None] | None = None
        startup_msg = await receive()
        if startup_msg.get("type") != "lifespan.startup":
            return

        try:
            if self.lifespan_cm is not None:
                cm = self.lifespan_cm(None)
                await cm.__aenter__()
            await send({"type": "lifespan.startup.complete"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reflex lifespan startup failed")
            await send(
                {"type": "lifespan.startup.failed", "message": repr(exc)}
            )
            return

        shutdown_msg = await receive()
        if shutdown_msg.get("type") != "lifespan.shutdown":
            return

        try:
            if cm is not None:
                await cm.__aexit__(None, None, None)
            await send({"type": "lifespan.shutdown.complete"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reflex lifespan shutdown failed")
            await send(
                {"type": "lifespan.shutdown.failed", "message": repr(exc)}
            )


__all__ = ["DEFAULT_RESERVED_REFLEX_PREFIXES", "DjangoOuterDispatcher"]
