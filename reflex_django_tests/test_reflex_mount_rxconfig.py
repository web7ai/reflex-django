"""Reflex plugins and rx.Config from reflex_mount()."""

from __future__ import annotations

import sys

import pytest
from django.conf import settings

from reflex_django.mount.config import clear_mount_rx_config
from reflex_django.mount.registry import clear_mount_registry
from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django


_MOUNT_PLUGINS_URLCONF = "reflex_django_tests.test_reflex_mount_plugins_urls"


@pytest.fixture(autouse=True)
def _clear_registries() -> None:
    clear_mount_registry()
    clear_mount_rx_config()
    sys.modules.pop(_MOUNT_PLUGINS_URLCONF, None)
    yield
    clear_mount_registry()
    clear_mount_rx_config()
    sys.modules.pop(_MOUNT_PLUGINS_URLCONF, None)


def test_reflex_mount_registers_plugins_in_rx_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    monkeypatch.setattr(
        settings,
        "ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_plugins_urls",
        raising=False,
    )
    monkeypatch.setattr(settings, "RX_USE_RXCONFIG_FILE", False, raising=False)

    config = ensure_rxconfig_from_django()

    assert any(getattr(p, "marker", None) == "mount_test" for p in config.plugins)
    assert config.frontend_port == 3100


def test_reflex_mount_rx_config_used_when_settings_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    monkeypatch.setattr(
        settings,
        "ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_plugins_urls",
        raising=False,
    )
    monkeypatch.setattr(settings, "RX_USE_RXCONFIG_FILE", False, raising=False)

    config = ensure_rxconfig_from_django()
    assert config.frontend_port == 3100


def test_reflex_mount_invalid_rx_config_key_raises() -> None:
    from reflex_django.django.urls import reflex_mount

    with pytest.raises(ValueError, match="Unsupported"):
        reflex_mount(rx_config={"not_a_real_config_key": 1})
