"""Tests for install_reflex_django_integration and get_config patching."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from reflex_base.config import Config

from reflex_django.plugins import ReflexDjangoPlugin
from reflex_django.runtime.integration import (
    _patch_reflex_compile,
    install_plugin_integration,
    install_reflex_django_integration,
    reset_integration_for_tests,
)
from reflex_django.mount.config import clear_mount_registration


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_registration()


def test_install_plugin_integration_marks_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "auto_mount": False,
        }
    )

    install_plugin_integration(plugin)

    from reflex_django.runtime.integration.registry import is_installed

    assert is_installed()


def test_configure_django_bootstraps_plugin_integration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Worker processes bootstrap via configure_django when rxconfig has a plugin."""
    rxconfig = tmp_path / "rxconfig.py"
    rxconfig.write_text(
        'import reflex as rx\n'
        'from reflex_django.plugins import ReflexDjangoPlugin\n'
        'config = rx.Config(\n'
        '    app_name="frontend",\n'
        '    frontend_port=4000,\n'
        '    plugins=[ReflexDjangoPlugin(config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False})],\n'
        ')\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    reset_integration_for_tests()
    if "rxconfig" in sys.modules:
        del sys.modules["rxconfig"]

    try:
        from reflex_base.config import get_config
        from reflex_django.runtime.integration.detect import detect_reflex_django_plugin
        from reflex_django.runtime.integration import install_plugin_integration
        from reflex_django.setup.conf import configure_django

        config = get_config(reload=True)
        plugin = detect_reflex_django_plugin(config)
        assert plugin is not None
        install_plugin_integration(plugin)
        configure_django()

        from reflex_django.runtime.integration.registry import is_installed

        assert is_installed()
        cfg = get_config()
        assert cfg.frontend_port == 4000
        assert cfg.app_name == "frontend"
    finally:
        sys.path.remove(str(tmp_path))


def test_install_reflex_django_integration_detects_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    plugin = ReflexDjangoPlugin(
        config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False}
    )
    config = Config(app_name="frontend", plugins=[plugin], _skip_plugins_checks=True)
    monkeypatch.setattr(
        "reflex_django.runtime.integration.call_original_get_config",
        lambda reload=False: config,
    )

    install_reflex_django_integration()

    from reflex_django.runtime.integration.registry import is_installed

    assert is_installed()


def test_compile_wrapper_calls_original_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped ``reflex._compile_app`` delegates compile to Reflex after prep work."""
    import reflex.reflex as reflex_module

    original_compile = mock.MagicMock()

    monkeypatch.setattr(reflex_module, "_reflex_django_compile_patched", False)
    monkeypatch.setattr(reflex_module, "_compile_app", original_compile)
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.prepare_pages_for_compile",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.load_app_factory",
        mock.MagicMock(return_value=mock.MagicMock()),
    )
    monkeypatch.setattr(
        "reflex_django.runtime.compile_validate.expected_dispatch_keys_from_app",
        lambda app: set(),
    )
    monkeypatch.setattr(
        "reflex_django.runtime.compile_validate.missing_frontend_dispatchers",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "reflex_django.runtime.compile_validate.warn_if_frontend_dispatchers_out_of_sync",
        lambda **kwargs: None,
    )

    _patch_reflex_compile()
    reflex_module._compile_app(avoid_dirty_check=False)

    original_compile.assert_called_once()


def test_compile_or_validate_wrapper_forwards_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped ``compile_or_validate_app`` forwards Reflex kwargs unchanged."""
    import reflex.utils.prerequisites as prerequisites

    original = mock.MagicMock(return_value=True)
    finalize = mock.MagicMock(return_value=True)

    monkeypatch.setattr(
        prerequisites,
        "_reflex_django_compile_or_validate_patched",
        False,
        raising=False,
    )
    monkeypatch.setattr(prerequisites, "compile_or_validate_app", original)
    monkeypatch.setattr(
        "reflex_django.dev.vite_proxy.finalize_web_dev_layout",
        finalize,
    )

    from reflex_django.runtime.integration import _patch_compile_or_validate_app

    _patch_compile_or_validate_app()
    result = prerequisites.compile_or_validate_app(
        compile=True,
        check_if_schema_up_to_date=True,
        trigger="initial",
    )

    assert result is True
    original.assert_called_once_with(
        compile=True,
        check_if_schema_up_to_date=True,
        prerender_routes=False,
        trigger="initial",
    )
    finalize.assert_not_called()


def test_app_compile_wrapper_finalizes_web_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped ``App._compile`` restores Vite proxy wiring after backend hot reload."""
    from reflex.app import App

    original = mock.MagicMock(return_value=None)
    finalize = mock.MagicMock(return_value=True)

    monkeypatch.setattr(App, "_reflex_django_app_compile_patched", False, raising=False)
    monkeypatch.setattr(App, "_compile", original)
    monkeypatch.setattr(
        "reflex_django.dev.vite_proxy.finalize_web_dev_layout",
        finalize,
    )

    from reflex_django.runtime.integration import _patch_app_compile

    _patch_app_compile()
    App._compile(mock.MagicMock(), trigger="hot_reload")

    original.assert_called_once()
    finalize.assert_called_once_with(force=True)


def test_vite_config_generation_injects_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated ``vite.config.js`` includes proxy wiring before disk write."""
    import reflex.utils.frontend_skeleton as frontend_skeleton

    monkeypatch.setattr(
        frontend_skeleton,
        "_reflex_django_vite_config_patched",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        frontend_skeleton,
        "_compile_vite_config",
        lambda config: "export default defineConfig({ plugins: [reactRouter()], server: {} });",
    )
    monkeypatch.setattr(
        "reflex_django.dev.proxy.dev_uses_separate_ports",
        lambda: True,
    )
    from reflex_django.dev.vite_proxy import ViteProxyRoute
    from reflex_django.runtime.integration import _patch_vite_config_generation

    routes = (
        ViteProxyRoute(
            target="http://127.0.0.1:8010",
            prefixes=("/admin", "/_event"),
        ),
    )
    monkeypatch.setattr(
        "reflex_django.dev.vite_proxy.resolve_vite_dev_proxy_routes",
        lambda: routes,
    )

    _patch_vite_config_generation()
    content = frontend_skeleton._compile_vite_config(mock.MagicMock())

    assert "reflexDjangoProxyPlugin()" in content
    assert '"/admin":' in content
