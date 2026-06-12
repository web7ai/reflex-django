"""Django-only ASGI entry for the separate HTTP subprocess in REFLEX_OUTER mode."""

from __future__ import annotations

from typing import Any

from reflex_django.asgi.app import ASGIApp, django_asgi_application


def build_django_http_application() -> ASGIApp:
    return django_asgi_application()


_application: ASGIApp | None = None


def _ensure_application() -> ASGIApp:
    global _application
    if _application is None:
        _application = build_django_http_application()
    return _application


async def application(scope: Any, receive: Any, send: Any) -> Any:
    await _ensure_application()(scope, receive, send)


__all__ = ["application", "build_django_http_application"]
