"""URLconf fixture mirroring a multi-route Django + Reflex project."""

from __future__ import annotations

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView


def _legacy_dashboard_redirect(request, remainder: str = ""):  # noqa: ANN001
    target = f"/{remainder.rstrip('/')}" if remainder else "/"
    return redirect(target, permanent=False)


def _noop_view(request):  # noqa: ANN001
    return redirect("/")


urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs", permanent=False), name="backend_root"),
    path("admin/rosetta/", admin.site.urls),
    path("admin/", admin.site.urls),
    path(
        "rosetta/",
        RedirectView.as_view(url="/admin/rosetta/", permanent=False),
        name="rosetta-legacy-redirect",
    ),
    path("impersonate/", admin.site.urls),
    path("api/", admin.site.urls),
    path("payments/webhook/stripe/", _noop_view, name="stripe_webhook_legacy"),
    path("dashboard/", _legacy_dashboard_redirect, name="dashboard_legacy_redirect"),
    path("dashboard/<path:remainder>", _legacy_dashboard_redirect),
]
