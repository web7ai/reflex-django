"""Catch-all Django view marking URL space owned by the Reflex SPA."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views import View


class ReflexMountView(View):
    """Placeholder view for Reflex catch-all URL patterns.

    In ``django_led`` routing mode the outer ASGI dispatcher forwards SPA
    traffic to Reflex directly. This view exists so ``urlpatterns`` document
    ownership and support ``reverse()``; it should not normally handle HTTP in
    production when using ``manage.py run_reflex``.
    """

    http_method_names = ["get", "head", "options"]

    def get(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        return HttpResponse(
            "This URL is served by the Reflex application. "
            "Use `python manage.py run_reflex` for local development.",
            status=501,
            content_type="text/plain",
        )

    def head(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        return HttpResponse(status=501)
