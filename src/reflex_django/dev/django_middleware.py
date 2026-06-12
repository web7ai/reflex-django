"""Django HTTP middleware for Reflex + Vite local development.

Use when Django admin or API routes are proxied through the Vite dev server
(``http://localhost:3000``) while the ASGI backend listens on another port
(typically ``8000``). Add near the top of ``MIDDLEWARE`` in your dev settings::

    MIDDLEWARE = [
        "reflex_django.dev.django_middleware.EnsureRequestBodyAttrsMiddleware",
        "reflex_django.dev.django_middleware.DevViteProxyHostMiddleware",
        *MIDDLEWARE,
    ]

Also set ``USE_X_FORWARDED_HOST = True`` and include both backend and frontend
origins in ``CSRF_TRUSTED_ORIGINS``.

Documentation: https://web7ai.github.io/reflex-django/local_development/
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from django.http import HttpRequest, HttpResponse

__all__ = [
    "DEFAULT_DEV_MIDDLEWARE",
    "DevViteProxyHostMiddleware",
    "EnsureRequestBodyAttrsMiddleware",
]

DEFAULT_DEV_MIDDLEWARE: tuple[str, ...] = (
    "reflex_django.dev.django_middleware.EnsureRequestBodyAttrsMiddleware",
    "reflex_django.dev.django_middleware.DevViteProxyHostMiddleware",
)

_LOCAL_DEV_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "[::1]"})


class DevViteProxyHostMiddleware:
    """Set ``X-Forwarded-Host`` from ``Origin``/``Referer`` when the Vite proxy omits it.

    Django admin on ``http://localhost:3000/admin`` must build forms and CSRF cookies
    for port ``3000``, not the backend ``Host`` header (e.g. ``localhost:8000``).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.META.get("HTTP_X_FORWARDED_HOST"):
            origin = request.META.get("HTTP_ORIGIN") or request.META.get(
                "HTTP_REFERER", ""
            )
            if origin:
                parsed = urlparse(origin)
                if parsed.netloc and parsed.hostname in _LOCAL_DEV_HOSTNAMES:
                    request.META["HTTP_X_FORWARDED_HOST"] = parsed.netloc
                    if parsed.scheme:
                        request.META["HTTP_X_FORWARDED_PROTO"] = parsed.scheme
        return self.get_response(request)


class EnsureRequestBodyAttrsMiddleware:
    """Set Django 6 request body attrs when missing (reflex-django synthetic requests).

    Only stub an empty body for requests with no payload. Setting ``_body`` on real
    POSTs (e.g. Django admin saves) breaks CSRF verification and form parsing.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not hasattr(request, "_read_started"):
            request._read_started = False  # type: ignore[attr-defined]
        if not hasattr(request, "_body"):
            content_length = request.META.get("CONTENT_LENGTH") or "0"
            try:
                has_body = int(content_length) > 0
            except (TypeError, ValueError):
                has_body = False
            if not has_body:
                request._body = b""  # type: ignore[attr-defined]
        return self.get_response(request)
