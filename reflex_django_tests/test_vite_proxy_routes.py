"""Tests for multi-target Vite dev proxy route resolution."""

from __future__ import annotations

import pytest

from reflex_django.core.constants import RESERVED_REFLEX_PREFIXES
from reflex_django.routing import UrlRoutingMode
from reflex_django.vite_proxy import (
    ViteProxyRoute,
    render_proxy_plugin_js,
    resolve_vite_dev_proxy_routes,
)


def test_resolve_routes_django_outer_uses_single_backend_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_URL_ROUTING", "django_outer")
    monkeypatch.setenv(
        "REFLEX_DJANGO_DJANGO_PREFIX",
        '["/admin", "/api"]',
    )

    class _Cfg:
        api_url = "http://127.0.0.1:8000"
        frontend_port = 3000
        backend_port = 8000

    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: _Cfg(),
    )

    routes = resolve_vite_dev_proxy_routes()
    assert len(routes) == 1
    assert routes[0].target == "http://127.0.0.1:8000"
    assert "/admin" in routes[0].prefixes
    assert "/api" in routes[0].prefixes
    assert "/_event" in routes[0].prefixes


def test_resolve_routes_reflex_outer_splits_django_and_reflex_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_URL_ROUTING", "reflex_outer")
    monkeypatch.setenv(
        "REFLEX_DJANGO_DJANGO_PREFIX",
        '["/admin", "/api"]',
    )
    monkeypatch.setenv("REFLEX_DJANGO_HTTP_PORT", "8001")

    class _Cfg:
        api_url = "http://127.0.0.1:8000"
        frontend_port = 3000
        backend_port = 8000

    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: _Cfg(),
    )

    routes = resolve_vite_dev_proxy_routes()
    assert len(routes) == 2
    django_route = next(r for r in routes if "/api" in r.prefixes)
    reflex_route = next(r for r in routes if "/_event" in r.prefixes)
    assert django_route.target == "http://127.0.0.1:8001"
    assert reflex_route.target == "http://127.0.0.1:8000"
    assert "/admin" in django_route.prefixes
    assert set(reflex_route.prefixes) == set(RESERVED_REFLEX_PREFIXES)


def test_render_proxy_plugin_js_supports_multiple_targets() -> None:
    source = render_proxy_plugin_js(
        routes=(
            ViteProxyRoute(
                target="http://127.0.0.1:8001",
                prefixes=("/api",),
            ),
            ViteProxyRoute(
                target="http://127.0.0.1:8000",
                prefixes=("/_event",),
            ),
        )
    )
    assert "const ROUTES" in source
    assert "http://127.0.0.1:8001" in source
    assert "http://127.0.0.1:8000" in source