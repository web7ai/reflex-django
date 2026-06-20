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
from reflex_django.mount.integration_config import (
    IntegrationConfig,
    clear_integration_config,
    get_integration_config,
    mount_enabled,
    resolve_and_cache_integration_config,
    set_integration_config,
)
from reflex_django.plugins import ReflexDjangoPlugin, RXDJANGOPLUGIN
from reflex_django.setup.errors import ConfigurationError
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
            "mount": {
                "enabled": True,
                "django_prefix": ("/admin", "/api"),
                "mount_prefix": "/",
            },
            "settings_module": "reflex_django_tests.django_settings",
        }
    )
    resolve_and_cache_integration_config(plugin)
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
    clear_url_caches()

    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "mount": {"enabled": True, "django_prefix": ("/admin",)},
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
        "import reflex as rx\n"
        "from reflex_django.plugins import ReflexDjangoPlugin\n"
        "config = rx.Config(\n"
        '    app_name="plugintest",\n'
        '    plugins=[ReflexDjangoPlugin(config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False})],\n'
        ")\n",
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
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "auto_mount": False,
        }
    )
    assert not is_installed()
    plugin.pre_compile()
    assert is_installed()


def test_register_mount_from_plugin_ignores_non_plugin() -> None:
    class NotAPlugin:
        config = {"django_prefix": ("/nope",)}

    register_mount_from_plugin(NotAPlugin())
    assert not get_merged_mount_registration().django_prefix


def test_embed_disabled_skips_dispatcher(
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
    clear_url_caches()

    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "django_prefix": ("/admin",),
            "embed": {"enabled": False},
            "proxy": {"server": "http://127.0.0.1:8000"},
        }
    )
    install_plugin_integration(plugin)

    app = rx.App()
    apply_django_integration(app)

    assert not getattr(app, "_reflex_django_dispatcher_configured", False)


def test_bridge_disabled_skips_event_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reflex as rx

    monkeypatch.setattr(settings, "RX_PROXY_SERVER", "", raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", False, raising=False)

    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "bridge": {"enabled": False},
        }
    )
    install_plugin_integration(plugin)

    app = rx.App()
    apply_django_integration(app)

    middleware_names = [type(m).__name__ for m in getattr(app, "_middlewares", ())]
    assert "DjangoEventBridge" not in middleware_names


class _IntegrationHolder:
    def __init__(self, config: dict) -> None:
        self.config = config


def test_integration_default_integrated_profile() -> None:
    from django.test import override_settings

    with override_settings(RX_AUTO_MOUNT=True, RX_PROXY_SERVER=""):
        config = IntegrationConfig.from_plugin(_IntegrationHolder({}))
    assert config.embed.enabled is True
    assert config.mount.enabled is True
    assert config.proxy.enabled is True
    assert config.bridge.enabled is True


def test_integration_split_dev_requires_server_at_runtime() -> None:
    config = IntegrationConfig.from_plugin(_IntegrationHolder({"profile": "split_dev"}))
    assert config.embed.enabled is False
    with pytest.raises(ConfigurationError, match="proxy.server"):
        config.validate(runtime=True)


def test_integration_split_dev_with_server() -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder(
            {
                "profile": "split_dev",
                "proxy": {"server": "http://127.0.0.1:8000"},
            }
        )
    )
    config.validate(runtime=True)
    assert config.proxy.server == "http://127.0.0.1:8000"


def test_integration_reflex_only_profile() -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder({"profile": "reflex_only"})
    )
    assert config.embed.enabled is False
    assert config.mount.enabled is False
    assert config.bridge.enabled is False


def test_integration_legacy_auto_mount_false() -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder(
            {
                "auto_mount": False,
                "django_prefix": ("/admin",),
            }
        )
    )
    assert config.mount.enabled is False
    assert config.mount.django_prefix is None


def test_integration_proxy_server_from_settings() -> None:
    from django.test import override_settings

    with override_settings(RX_PROXY_SERVER="http://127.0.0.1:9000"):
        config = IntegrationConfig.from_plugin(_IntegrationHolder({}))
    assert config.embed.enabled is False
    assert config.proxy.server == "http://127.0.0.1:9000"


def test_integration_invalid_bridge_mode() -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder({"bridge": {"mode": "invalid"}})
    )
    with pytest.raises(ConfigurationError, match="Invalid bridge.mode"):
        config.validate()


def test_integration_invalid_embed_pillar_key() -> None:
    with pytest.raises(ValueError, match="config\\['embed'\\]"):
        IntegrationConfig.from_plugin(_IntegrationHolder({"embed": {"nope": True}}))


def test_integration_resolve_and_cache() -> None:
    plugin = ReflexDjangoPlugin(
        config={
            "embed": {"enabled": True},
            "mount": {"enabled": False},
        }
    )
    cached = resolve_and_cache_integration_config(plugin)
    assert get_integration_config() is cached
    assert cached.mount.enabled is False


def test_mount_enabled_prefers_cached_config_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder({"mount": {"enabled": False}})
    )
    set_integration_config(config)
    monkeypatch.setenv("RX_AUTO_MOUNT", "1")
    assert mount_enabled() is False


def test_mount_disabled_ignores_plugin_django_prefix() -> None:
    plugin = ReflexDjangoPlugin(
        config={
            "mount": {"enabled": False, "django_prefix": ("/admin", "/api")},
            "mount_prefix": "/",
        }
    )
    resolve_and_cache_integration_config(plugin)
    assert get_integration_config().mount.django_prefix is None
    register_mount_from_plugin(plugin)
    assert get_merged_mount_registration().django_prefix is None


def test_mount_disabled_skips_embed_dispatcher(
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
    clear_url_caches()

    plugin = ReflexDjangoPlugin(
        config={
            "settings_module": "reflex_django_tests.django_settings",
            "mount": {"enabled": False, "django_prefix": ("/admin",)},
        }
    )
    install_plugin_integration(plugin)

    app = rx.App()
    apply_django_integration(app)

    assert not getattr(app, "_reflex_django_dispatcher_configured", False)


def test_integration_summary_string() -> None:
    config = IntegrationConfig.from_plugin(
        _IntegrationHolder(
            {
                "embed": {"enabled": False},
                "proxy": {"server": "http://127.0.0.1:8000"},
                "bridge": {"mode": "smart"},
            }
        )
    )
    assert "embed=off" in config.summary()
    assert "127.0.0.1:8000" in config.summary()


def test_integration_plugin_rejects_invalid_nested_key() -> None:
    with pytest.raises(ValueError, match="config\\['proxy'\\]"):
        ReflexDjangoPlugin(config={"proxy": {"bad_key": True}})
