"""Tests for Vite dev-server proxy injection."""

from __future__ import annotations

from reflex_django.dev.vite_proxy import (
    ViteProxyRoute,
    inject_vite_dev_proxy,
    inject_vite_proxy_plugin,
    patch_vite_config,
    patch_vite_config_content,
    strip_vite_config_proxy,
)

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


def test_strip_vite_config_proxy_removes_injected_rules() -> None:
    patched = patch_vite_config(
        _SAMPLE_VITE_CONFIG,
        target="http://localhost:8000",
        prefixes=("/admin", "/api"),
    )
    stripped = strip_vite_config_proxy(patched)
    assert "reflex-django-proxy" not in stripped
    assert "reflexDjangoProxyPlugin" not in stripped
    assert '"/_event":' not in stripped
    assert "server: {" in stripped


def test_inject_vite_proxy_plugin_adds_call_when_only_import_present() -> None:
    content = """import { reflexDjangoProxyPlugin } from "./vite-plugin-reflex-django-proxy.js";
export default defineConfig((config) => ({
  server: {
    port: process.env.PORT,
  },
  plugins: [
    reactRouter(),
  ],
}));
"""
    patched = inject_vite_proxy_plugin(content)
    assert "reflexDjangoProxyPlugin()" in patched


def test_patch_vite_config_content_adds_revision_stamp() -> None:
    sample = """export default defineConfig((config) => ({
  server: {
    port: process.env.PORT,
  },
  plugins: [
    reactRouter(),
  ],
}));
"""
    routes = (
        ViteProxyRoute(
            target="http://localhost:8000",
            prefixes=("/admin", "/_event"),
        ),
    )
    result = patch_vite_config_content(sample, routes=routes)
    assert "reflexDjangoProxyPlugin()" in result
    assert "rx-django-proxy-rev:" in result
    assert '"/admin":' in result
