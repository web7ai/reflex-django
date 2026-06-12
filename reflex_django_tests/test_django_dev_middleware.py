"""Tests for reflex-django Django dev HTTP middleware."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from reflex_django.dev.django_middleware import (
    DEFAULT_DEV_MIDDLEWARE,
    DevViteProxyHostMiddleware,
    EnsureRequestBodyAttrsMiddleware,
)


def _middleware_response(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def test_default_dev_middleware_paths() -> None:
    assert len(DEFAULT_DEV_MIDDLEWARE) == 2
    assert all(p.startswith("reflex_django.dev.django_middleware.") for p in DEFAULT_DEV_MIDDLEWARE)


def test_ensure_request_body_attrs_stubs_empty_body() -> None:
    factory = RequestFactory()
    request = factory.get("/")
    del request._body  # type: ignore[attr-defined]

    mw = EnsureRequestBodyAttrsMiddleware(_middleware_response)
    mw(request)

    assert request._body == b""  # type: ignore[attr-defined]
    assert request._read_started is False  # type: ignore[attr-defined]


def test_ensure_request_body_attrs_does_not_clear_post_body() -> None:
    factory = RequestFactory()
    request = factory.post("/", data={"csrfmiddlewaretoken": "x"}, content_type="application/x-www-form-urlencoded")

    mw = EnsureRequestBodyAttrsMiddleware(_middleware_response)
    mw(request)

    assert len(request.body) > 0


def test_dev_vite_proxy_host_from_origin() -> None:
    factory = RequestFactory()
    request = factory.get(
        "/admin/",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_HOST="localhost:8000",
    )

    mw = DevViteProxyHostMiddleware(_middleware_response)
    mw(request)

    assert request.META["HTTP_X_FORWARDED_HOST"] == "localhost:3000"
    assert request.META["HTTP_X_FORWARDED_PROTO"] == "http"


def test_dev_vite_proxy_host_skips_when_already_set() -> None:
    factory = RequestFactory()
    request = factory.get(
        "/admin/",
        HTTP_ORIGIN="http://localhost:3000",
        HTTP_X_FORWARDED_HOST="frontend:3000",
    )

    mw = DevViteProxyHostMiddleware(_middleware_response)
    mw(request)

    assert request.META["HTTP_X_FORWARDED_HOST"] == "frontend:3000"
