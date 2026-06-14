"""Tests for multi-target Vite dev proxy route resolution."""

from __future__ import annotations

import pytest

from reflex_django.core.constants import RESERVED_REFLEX_PREFIXES
from reflex_django.dev.vite_proxy import (
    ViteProxyRoute,
    render_proxy_plugin_js,
    resolve_vite_dev_proxy_routes,
)


def test_resolve_routes_use_reflex_backend_when_proxy_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    monkeypatch.setenv(
        "RX_DJANGO_PREFIX",
        '["/admin", "/api"]',
    )

    class _Cfg:
        api_url = "http://127.0.0.1:8010"
        frontend_port = 3000
        backend_port = 8010

    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: _Cfg(),
    )

    routes = resolve_vite_dev_proxy_routes()
    assert len(routes) == 1
    assert routes[0].target == "http://127.0.0.1:8010"
    assert "/admin" in routes[0].prefixes
    assert "/_event" in routes[0].prefixes


def test_resolve_routes_splits_django_and_reflex_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RX_PROXY_SERVER", "http://127.0.0.1:8000")
    monkeypatch.setenv(
        "RX_DJANGO_PREFIX",
        '["/admin", "/api"]',
    )

    class _Cfg:
        api_url = "http://127.0.0.1:8010"
        frontend_port = 3000
        backend_port = 8010

    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda: _Cfg(),
    )

    routes = resolve_vite_dev_proxy_routes()
    assert len(routes) == 2
    django_route = next(r for r in routes if "/api" in r.prefixes)
    reflex_route = next(r for r in routes if "/_event" in r.prefixes)
    assert django_route.target == "http://127.0.0.1:8000"
    assert reflex_route.target == "http://127.0.0.1:8010"
    assert "/admin" in django_route.prefixes
    assert set(reflex_route.prefixes) == set(RESERVED_REFLEX_PREFIXES)


def test_render_proxy_plugin_js_supports_multiple_targets() -> None:
    source = render_proxy_plugin_js(
        routes=(
            ViteProxyRoute(
                target="http://127.0.0.1:8000",
                prefixes=("/api",),
            ),
            ViteProxyRoute(
                target="http://127.0.0.1:8010",
                prefixes=("/_event",),
            ),
        )
    )
    assert "http://127.0.0.1:8000" in source
    assert "http://127.0.0.1:8010" in source
    assert "/_event" in source
