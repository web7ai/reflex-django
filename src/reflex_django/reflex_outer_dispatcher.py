"""ASGI dispatcher for :attr:`~reflex_django.routing.UrlRoutingMode.REFLEX_OUTER`.

Reflex owns the public port; Django admin/API/static HTTP is proxied to a
separate Django HTTP worker (``reflex_django.django_http_entry``).
"""

from __future__ import annotations

import logging

from reflex_django.asgi import (
    ASGIApp,
    ASGIReceive,
    ASGIScope,
    ASGISend,
    _is_reserved_reflex_path,
    _should_route_to_django,
)

logger = logging.getLogger("reflex_django.reflex_outer_dispatcher")


class ReflexOuterDispatcher:
    """Route Django-owned prefixes to the HTTP worker; everything else to Reflex."""

    def __init__(
        self,
        *,
        reflex: ASGIApp,
        django: ASGIApp,
        django_prefixes: tuple[str, ...],
    ) -> None:
        self.reflex = reflex
        self.django = django
        self.django_prefixes = tuple(
            p for p in django_prefixes if p and str(p).strip()
        )

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self.reflex(scope, receive, send)
            return

        if scope_type not in ("http", "websocket"):
            return

        path = scope.get("path", "") or "/"

        if _should_route_to_django(scope, path, self.django_prefixes):
            await self.django(scope, receive, send)
            return

        if scope_type == "websocket" and not _is_reserved_reflex_path(path):
            await send({"type": "websocket.close", "code": 1008})
            return

        await self.reflex(scope, receive, send)


__all__ = ["ReflexOuterDispatcher"]