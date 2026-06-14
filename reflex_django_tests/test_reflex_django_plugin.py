"""Tests for Reflex-first ReflexDjangoPlugin integration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import clear_url_caches
from reflex_base.config import Config

from reflex_django.bootstrap.app_setup import apply_django_integration
from reflex_django.mount.config import (
    clear_mount_rx_config,
    get_merged_mount_rx_config,
    register_mount_from_plugin,
)
from reflex_django.plugins import ReflexDjangoPlugin, RXDJANGOPLUGIN
from reflex_django.runtime.integration import (
    install_reflex_first_integration,
    reset_integration_for_tests,
)
from reflex_django.runtime.integration.modes import (
    IntegrationMode,
    clear_active_integration_mode,
    detect_reflex_django_plugin,
    resolve_integration_mode,
)
from reflex_django.runtime.integration.registry import (
    install_early_cli_patch,
    is_installed,
)
from reflex_django.setup.conf import configure_django


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    reset_integration_for_tests()
    clear_mount_rx_config()
    clear_active_integration_mode()
    yield
    reset_integration_for_tests()
    clear_mount_rx_config()
    clear_active_integration_mode()


def test_rxdjangoplugin_alias() -> None:
    assert RXDJANGOPLUGIN is ReflexDjangoPlugin


def test_invalid_plugin_config_keys() -> None:
    with pytest.raises(ValueError, match="Unsupported ReflexDjangoPlugin config keys"):
        ReflexDjangoPlugin(config={"not_a_real_key": True})


def test_plugin_registers_mount_config() -> None:
    plugin = ReflexDjangoPlugin(
        config={
            "django_prefix": ("/admin", "/api"),
            "mount_prefix": "/",
            "settings_module": "reflex_django_tests.django_settings",
        }
    )
    register_mount_from_plugin(plugin)
    mount = get_merged_mount_rx_config()
    assert mount.django_prefix == ("/admin", "/api")
    assert mount.mount_prefix == "/"
    assert mount.django_plugin.get("settings_module") == "reflex_django_tests.django_settings"


def test_detect_reflex_django_plugin() -> None:
    plugin = ReflexDjangoPlugin()
    config = Config(app_name="demo", plugins=[plugin], _skip_plugins_checks=True)
    assert detect_reflex_django_plugin(config) is plugin


def test_mode_detection_priority_plugin_over_django(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    plugin = ReflexDjangoPlugin()
    config = Config(app_name="demo", plugins=[plugin], _skip_plugins_checks=True)
    assert resolve_integration_mode(config=config) == IntegrationMode.REFLEX_FIRST


def test_mode_detection_django_first_without_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    config = Config(app_name="demo", plugins=[], _skip_plugins_checks=True)
    assert resolve_integration_mode(config=config) == IntegrationMode.DJANGO_FIRST


def test_plugin_post_compile_mounts_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reflex as rx

    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    monkeypatch.setattr(settings, "RX_PROXY_SERVER", "", raising=False)
    monkeypatch.setattr(
        settings,
        "ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_admin_urls",
        raising=False,
    )
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", False, raising=False)
    clear_url_caches()

    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "django_prefix": ("/admin",),
            "auto_mount": False,
            "urlconf": "reflex_django_tests.test_reflex_mount_admin_urls",
        }
    )
    install_reflex_first_integration(plugin)

    app = rx.App()
    apply_django_integration(app)

    assert getattr(app, "_reflex_django_dispatcher_configured", False)
    assert app.api_transformer


def test_reflex_first_skips_rxconfig_synthesis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rxconfig = tmp_path / "rxconfig.py"
    rxconfig.write_text(
        'import reflex as rx\n'
        'from reflex_django.plugins import ReflexDjangoPlugin\n'
        'config = rx.Config(\n'
        '    app_name="plugintest",\n'
        '    plugins=[ReflexDjangoPlugin(config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False})],\n'
        ')\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    try:
        if "rxconfig" in sys.modules:
            del sys.modules["rxconfig"]

        install_early_cli_patch()
        from reflex_base.config import get_config

        config = get_config(reload=True)
        assert config.app_name == "plugintest"
        assert is_installed()
        mod = sys.modules.get("rxconfig")
        assert mod is not None
        assert getattr(mod, "__file__", None) == str(rxconfig)
    finally:
        sys.path.remove(str(tmp_path))


def test_django_first_unchanged_without_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    monkeypatch.setattr(settings, "RX_CONFIG", {"app_name": "demofirst"}, raising=False)
    configure_django()

    from reflex_django.runtime.integration import install_django_first_integration
    from reflex_django.runtime.integration.modes import get_active_integration_mode

    install_django_first_integration()
    assert get_active_integration_mode() == IntegrationMode.DJANGO_FIRST
    assert is_installed()

    from reflex_base.config import get_config

    merged = get_config()
    assert merged.app_name == "demofirst"


def test_plugin_pre_compile_triggers_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    plugin = ReflexDjangoPlugin(
        config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False}
    )
    assert not is_installed()
    plugin.pre_compile()
    assert is_installed()


def test_register_mount_from_plugin_ignores_non_plugin() -> None:
    class NotAPlugin:
        config = {"django_prefix": ("/nope",)}

    register_mount_from_plugin(NotAPlugin())
    assert not get_merged_mount_rx_config().django_plugin