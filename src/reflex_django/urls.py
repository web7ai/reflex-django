"""Default URL conf and helpers for reflex-django.

Use :func:`reflex_mount` as the **last** entry in ``urlpatterns`` for Django-led SPA
routing. Register Django routes (admin, API, …) **before** ``reflex_mount`` and list
their path prefixes in ``django_prefix``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from django.contrib import admin
from django.urls import URLPattern, path, re_path
from django.views.generic import RedirectView

from reflex_django.mount_config import register_mount_rx_config
from reflex_django.mount_registry import register_mount
from reflex_django.prefixes import export_prefix_env, resolve_prefixes
from reflex_django.views.mount import ReflexMountView


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

    Wire **before** :func:`reflex_mount` and include ``admin_prefix`` in
    ``django_prefix`` (for example ``django_prefix=("/admin", "/api")``).

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
    app_name: str | None = None,
    mount_prefix: str = "/",
    django_prefix: str | tuple[str, ...] = (),
    plugins: Sequence[Any] | None = None,
    rx_config: Mapping[str, Any] | None = None,
    django_plugin: Mapping[str, Any] | None = None,
) -> URLPattern:
    """Return the SPA catch-all pattern and register Reflex ``rx.Config``.

    Append to existing ``urlpatterns`` (keep this entry **last**)::

        urlpatterns = [path("admin/", admin.site.urls), ...]
        urlpatterns += [reflex_mount(django_prefix=("/admin", "/api"))]

    List the same path prefixes in ``django_prefix`` so ASGI routing and the
    catch-all exclude your Django routes.

    Args:
        app_name: Reflex application name (package label). Defaults to the Django
            project folder name (parent of ``manage.py``, with ``-`` → ``_``).
        mount_prefix: SPA catch-all prefix (default ``"/"``).
        django_prefix: Path prefix(es) owned by Django (for example
            ``("/admin", "/api", "/webhooks")``).
        plugins: Reflex :class:`~reflex_base.plugins.base.Plugin` instances.
        rx_config: ``rx.Config`` keyword arguments (ports, ``db_url``, …). You may
            include ``app_name`` here instead of the ``app_name`` argument.
        django_plugin: Keyword arguments for :class:`~reflex_django.ReflexDjangoPlugin`.

    Returns:
        A single catch-all :class:`~django.urls.URLPattern`.

    Example::

        from django.contrib import admin
        from django.urls import include, path
        from reflex_django.urls import reflex_mount

        urlpatterns = [
            path("admin/", admin.site.urls),
            path("api/", include("myapp.api_urls")),
        ]
        urlpatterns += [
            reflex_mount(
                app_name="myapp",
                mount_prefix="/",
                django_prefix=("/admin", "/api"),
                rx_config={"frontend_port": 3000, "backend_port": 8000},
            ),
        ]
    """
    from reflex_django.rxconfig_bridge import _coerce_rx_config_dict

    merged_rx = _coerce_rx_config_dict(dict(rx_config or {}))
    if app_name:
        merged_rx["app_name"] = app_name

    register_mount_rx_config(
        app_name=app_name or merged_rx.get("app_name"),
        plugins=plugins,
        rx_config=merged_rx,
        django_plugin=django_plugin,
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
    )

    from reflex_django.app_factory import import_mount_app_views

    import_mount_app_views(app_name or merged_rx.get("app_name"))

    config = resolve_prefixes(
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
    )
    export_prefix_env(config)

    return _reflex_catchall_pattern(
        config.mount_prefix,
        config.reserved_paths_for_catchall(),
    )


urlpatterns: list[URLPattern] = [reflex_mount()]
