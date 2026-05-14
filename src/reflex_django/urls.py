"""Default URL conf for reflex-django.

Reads the admin prefix from the active Django settings (which the plugin keeps
in sync with the ASGI dispatcher) and mounts :mod:`django.contrib.admin`.

For JSON or REST routes, set ``ROOT_URLCONF`` to your own module and add
``path("api/", ...)`` (or use :class:`reflex_django.ReflexDjangoPlugin`'s
``backend_prefix`` so the ASGI dispatcher forwards that prefix to Django).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import path


def _strip(prefix: str) -> str:
    return prefix.strip("/")


_admin_segment = _strip(getattr(settings, "REFLEX_DJANGO_ADMIN_PREFIX", "/admin"))

urlpatterns = [
    path(f"{_admin_segment}/" if _admin_segment else "", admin.site.urls),
]
