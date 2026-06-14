"""URLconf that appends reflex_mount via module-level urlpatterns +=."""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

from reflex_django.django.urls import reflex_mount

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", admin.site.urls),
]
urlpatterns += [
    reflex_mount(
        rx_config={"app_name": "fixture_app"},
    )
]
