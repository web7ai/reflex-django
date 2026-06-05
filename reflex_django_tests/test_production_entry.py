"""Boot-path tests for settings-driven auto-mount (ASGI / integration entry points)."""

from __future__ import annotations

import importlib

import pytest
from django.conf import settings
from django.urls import clear_url_caches

from reflex_django.auto_mount import (
    clear_auto_mount_state,
    maybe_auto_mount,
    register_mount_from_settings,
)
from reflex_django.mount_config import (
    clear_mount_rx_config,
    has_mount_rx_config,
    register_mount_rx_config,
)
from reflex_django.mount_registry import clear_mount_registry
from reflex_django.routing import UrlRoutingMode, resolve_url_routing
from reflex_django.views.mount import ReflexMountView


@pytest.fixture(autouse=True)
def _reset() -> None:
    clear_mount_registry()
    clear_mount_rx_config()
    clear_auto_mount_state()
    yield
    clear_mount_registry()
    clear_mount_rx_config()
    clear_auto_mount_state()


def test_register_mount_from_settings_before_ready() -> None:
    import django

    django.setup()
    assert not has_mount_rx_config()
    register_mount_from_settings()
    assert has_mount_rx_config()


def test_maybe_auto_mount_skips_reflex_led_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_auto_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "REFLEX_DJANGO_AUTO_MOUNT", True, raising=False)
    monkeypatch.setenv("REFLEX_DJANGO_URL_ROUTING", "reflex_led")
    import sys

    sys.modules.pop(urlconf_name, None)

    maybe_auto_mount()
    urlconf = importlib.import_module(urlconf_name)
    assert len(urlconf.urlpatterns) == 1
    assert resolve_url_routing() == UrlRoutingMode.REFLEX_LED


def test_install_reflex_django_integration_auto_mounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    from reflex_django.integration import install_reflex_django_integration

    urlconf_name = "reflex_django_tests.test_auto_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "REFLEX_DJANGO_AUTO_MOUNT", True, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)
    clear_auto_mount_state()

    install_reflex_django_integration()
    clear_url_caches()

    urlconf = importlib.import_module(urlconf_name)
    assert len(urlconf.urlpatterns) == 2
    from django.urls import resolve

    match = resolve("/spa/route")
    assert match.func.view_class is ReflexMountView


def test_ensure_mount_config_loaded_registers_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    from reflex_django.mount_config import ensure_mount_config_loaded

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_RX_CONFIG",
        {"app_name": "boot_test"},
        raising=False,
    )
    clear_mount_rx_config()
    ensure_mount_config_loaded()
    assert has_mount_rx_config()
