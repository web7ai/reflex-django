"""Tests for on-disk Vite proxy patching."""

from __future__ import annotations

from pathlib import Path

from reflex_django.dev.vite_proxy import (
    ViteProxyRoute,
    ensure_vite_django_dev_proxy,
    inject_vite_proxy_plugin,
    patch_vite_config,
    render_proxy_plugin_js,
    strip_vite_config_proxy,
)

_SAMPLE = """export default defineConfig({
  server: { port: 3000 },
  plugins: [
    reactRouter(),
  ],
});
"""


def test_render_proxy_plugin_js() -> None:
    source = render_proxy_plugin_js(
        target="http://localhost:8000",
        prefixes=("/admin", "/api"),
    )
    assert "reflex-django-proxy-plugin" in source
    assert '"/admin"' in source
    assert "http://localhost:8000" in source


def test_inject_vite_proxy_plugin() -> None:
    patched = inject_vite_proxy_plugin(_SAMPLE)
    assert "reflexDjangoProxyPlugin()" in patched
    assert "vite-plugin-reflex-django-proxy.js" in patched


def test_ensure_vite_django_dev_proxy_writes(tmp_path: Path) -> None:
    vite = tmp_path / "vite.config.js"
    vite.write_text(_SAMPLE, encoding="utf-8")
    updated = ensure_vite_django_dev_proxy(
        tmp_path,
        target="http://localhost:8000",
        prefixes=("/admin",),
    )
    assert updated is True
    assert (tmp_path / "vite-plugin-reflex-django-proxy.js").is_file()
    text = vite.read_text(encoding="utf-8")
    assert "reflexDjangoProxyPlugin()" in text
    assert "reflex-django-proxy" in text


def test_ensure_vite_django_dev_proxy_idempotent(tmp_path: Path) -> None:
    vite = tmp_path / "vite.config.js"
    vite.write_text(
        patch_vite_config(
            _SAMPLE,
            target="http://localhost:8000",
            prefixes=("/admin",),
        ),
        encoding="utf-8",
    )
    (tmp_path / "vite-plugin-reflex-django-proxy.js").write_text(
        render_proxy_plugin_js(
            target="http://localhost:8000",
            prefixes=("/admin",),
        ),
        encoding="utf-8",
    )
    assert (
        ensure_vite_django_dev_proxy(
            tmp_path,
            target="http://localhost:8000",
            prefixes=("/admin",),
        )
        is False
    )


def test_ensure_vite_django_dev_proxy_force_restores_stripped_config(
    tmp_path: Path,
) -> None:
    vite = tmp_path / "vite.config.js"
    routes = (
        ViteProxyRoute(
            target="http://127.0.0.1:8010",
            prefixes=("/admin", "/api", "/_event"),
        ),
    )
    vite.write_text(_SAMPLE, encoding="utf-8")
    ensure_vite_django_dev_proxy(tmp_path, routes=routes, force=True)
    first = vite.read_text(encoding="utf-8")
    assert "reflexDjangoProxyPlugin()" in first

    vite.write_text(strip_vite_config_proxy(first), encoding="utf-8")
    ensure_vite_django_dev_proxy(tmp_path, routes=routes, force=True)
    restored = vite.read_text(encoding="utf-8")
    assert "reflexDjangoProxyPlugin()" in restored
    assert "rx-django-proxy-rev:" in restored
