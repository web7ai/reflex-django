"""Tests for Vite dev-server proxy injection."""

from __future__ import annotations

from reflex_django.vite_proxy import inject_vite_dev_proxy, patch_vite_config

_SAMPLE_VITE_CONFIG = """export default defineConfig((config) => ({
  server: {
    port: process.env.PORT,
    hmr: true,
    watch: {
      ignored: [],
    },
  },
}));
"""


def test_inject_vite_dev_proxy_adds_entries() -> None:
    result = patch_vite_config(
        _SAMPLE_VITE_CONFIG,
        target="http://localhost:8000",
        prefixes=("/api", "/admin", "/billing"),
    )
    assert "reflex-django-proxy" in result
    assert '"http://localhost:8000"' in result
    assert '"/api":' in result
    assert '"/admin":' in result
    assert '"/billing":' in result
    assert '"/_event":' in result
    assert "ws: true" in result
    assert "changeOrigin: true" in result


def test_inject_vite_dev_proxy_idempotent() -> None:
    first = inject_vite_dev_proxy(
        _SAMPLE_VITE_CONFIG,
        target="http://localhost:8000",
        prefixes=("/admin",),
    )
    second = inject_vite_dev_proxy(
        first,
        target="http://localhost:9000",
        prefixes=("/admin", "/api"),
    )
    assert second.count("reflex-django-proxy") == 1
    assert "http://localhost:9000" in second
    assert '"/api":' in second


def test_inject_vite_dev_proxy_noop_without_prefixes() -> None:
    assert (
        inject_vite_dev_proxy(
            _SAMPLE_VITE_CONFIG,
            target="http://localhost:8000",
            prefixes=(),
        )
        == _SAMPLE_VITE_CONFIG
    )


def test_inject_vite_dev_proxy_normalizes_prefixes() -> None:
    result = inject_vite_dev_proxy(
        _SAMPLE_VITE_CONFIG,
        target="http://localhost:8000",
        prefixes=("api/", "/admin/"),
    )
    assert '"/api":' in result
    assert '"/admin":' in result
