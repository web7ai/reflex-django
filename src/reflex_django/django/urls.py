"""Default URL conf and helpers for reflex-django.

With ``RX_AUTO_MOUNT=True`` (default), the SPA catch-all is appended
automatically at startup. Use :func:`reflex_mount` only for overrides
(``mount_prefix``, ``django_prefix``, plugins).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from django.contrib import admin
from django.urls import URLPattern, path, re_path
from django.views.generic import RedirectView

from reflex_django.mount.registry import register_mount
from reflex_django.pages.decorators import page
from reflex_django.views.mount import ReflexMountView

__all__ = [
    "admin_urlpatterns",
    "page",
    "reflex_mount",
]


def _strip(prefix: str) -> str:
    return prefix.strip("/")


def _catchall_exclusions(reserved: tuple[str, ...]) -> str:
    """Negative lookaheads for reserved backend prefixes (with and without leading ``/``)."""
    parts: list[str] = []
    for path_prefix in reserved:
        parts.append(rf"(?!{re.escape(path_prefix)}$)")
        segment = path_prefix.lstrip("/")
        if segment:
            parts.append(rf"(?!{re.escape(segment)}$)")
            parts.append(rf"(?!{re.escape(segment)}/)")
    if "/" in reserved:
        parts.append(r"(?!$)")
    return "".join(parts)


def _catchall_regex(mount_prefix: str, reserved: tuple[str, ...]) -> str:
    """Build catch-all regex, excluding bare backend prefix paths."""
    exclusions = _catchall_exclusions(reserved)
    if mount_prefix == "/":
        return f"^{exclusions}.*$"
    escaped = re.escape(mount_prefix.rstrip("/"))
    return rf"^{escaped}(?:/.*)?$"


def _reflex_catchall_pattern(
    mount_prefix: str,
    reserved: tuple[str, ...],
) -> URLPattern:
    pattern = _catchall_regex(mount_prefix, reserved)
    register_mount(prefix=mount_prefix, pattern=pattern)
    return re_path(pattern, ReflexMountView.as_view(), name="reflex_mount")


def admin_urlpatterns(admin_prefix: str = "/admin") -> list[URLPattern]:
    """Optional admin redirect (no trailing slash) + ``admin.site.urls``.

    Wire **before** the Reflex SPA catch-all and include ``admin_prefix`` in
    ``django_prefix`` when using manual :func:`reflex_mount`.

    Args:
        admin_prefix: Normalized admin mount (default ``"/admin"``).

    Returns:
        URL patterns for Django admin.
    """
    if not admin_prefix:
        return []
    segment = _strip(admin_prefix)
    if not segment:
        return []
    trailing = f"/{segment}/"
    return [
        path(segment, RedirectView.as_view(url=trailing, permanent=False)),
        path(f"{segment}/", admin.site.urls),
    ]


def reflex_mount(
    *,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
    urlpatterns: Sequence[Any] | None = None,
):
    """Register mount prefixes and return the SPA catch-all URL handle.

    Use for URL overrides only::

        urlpatterns += reflex_mount(mount_prefix="/app")

    Args:
        mount_prefix: SPA catch-all prefix (default ``/``).
        django_prefix: Django-owned prefixes; ``None`` auto-detects from ``urlpatterns``.
        urlpatterns: Optional pattern list for prefix auto-detection.

    Returns:
        :class:`~reflex_django.mount.auto.ReflexMountHandle` (iterable; ``.urlpatterns``).
    """
    from reflex_django.mount.auto import ensure_reflex_mount

    if mount_prefix is None:
        mount_prefix = "/"
    return ensure_reflex_mount(
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
        urlpatterns=urlpatterns,
    )


urlpatterns: list[URLPattern] = []
