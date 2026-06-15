"""Tests for plugin-only ReflexDjangoPlugin integration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import clear_url_caches
from reflex_base.config import Config

from reflex_django.bootstrap.app_setup import apply_django_integration
from reflex_django.mount.config import (
    clear_mount_registration,
    get_merged_mount_registration,
    register_mount_from_plugin,
)
from reflex_django.plugins import ReflexDjangoPlugin, RXDJANGOPLUGIN
from reflex_django.runtime.integration import (
    install_plugin_integration,
    reset_integration_for_tests,
)
from reflex_django.runtime.integration.detect import detect_reflex_django_plugin
from reflex_django.runtime.integration.registry import is_installed


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    reset_integration_for_tests()
    clear_mount_registration()
    yield
    reset_integration_for_tests()
    clear_mount_registration()


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
    mount = get_merged_mount_registration()
    assert mount.django_prefix == ("/admin", "/api")
    assert mount.mount_prefix == "/"


def test_detect_reflex_django_plugin() -> None:
    plugin = ReflexDjangoPlugin()
    config = Config(app_name="demo", plugins=[plugin], _skip_plugins_checks=True)
    assert detect_reflex_django_plugin(config) is plugin


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
        }
    )
    install_plugin_integration(plugin)

    app = rx.App()
    apply_django_integration(app)

    assert getattr(app, "_reflex_django_dispatcher_configured", False)
    assert app.api_transformer


def test_plugin_get_config_bootstrap_from_rxconfig(
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

        reset_integration_for_tests()
        from reflex_base.config import get_config
        from reflex_django.runtime.integration.detect import detect_reflex_django_plugin

        config = get_config(reload=True)
        assert config.app_name == "plugintest"
        assert detect_reflex_django_plugin(config) is not None
        mod = sys.modules.get("rxconfig")
        assert mod is not None
        assert getattr(mod, "__file__", None) == str(rxconfig)
    finally:
        sys.path.remove(str(tmp_path))


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
    assert not get_merged_mount_registration().django_prefix
