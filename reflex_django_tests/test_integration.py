"""Tests for install_reflex_django_integration and get_config patching."""

from __future__ import annotations

import pytest

from reflex_django.integration import (
    install_reflex_django_integration,
    reset_integration_for_tests,
)
from reflex_django.mount_config import clear_mount_rx_config, register_mount_rx_config


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_rx_config()


def test_install_patches_get_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    register_mount_rx_config(
        app_name="frontend",
        rx_config={"frontend_port": 4000},
    )

    install_reflex_django_integration()

    from reflex_base.config import get_config

    cfg = get_config()
    assert cfg.frontend_port == 4000
    assert cfg.app_name == "frontend"
    assert any(
        type(p).__name__ == "ReflexDjangoPlugin" for p in (cfg.plugins or ())
    )


def test_configure_django_bootstraps_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Granian workers bootstrap via configure_django -> _bootstrap helper."""
    reset_integration_for_tests()
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    register_mount_rx_config(
        app_name="frontend",
        rx_config={"frontend_port": 4000},
    )

    from reflex_django.conf import configure_django, _bootstrap_reflex_integration_for_django_mode

    configure_django()
    _bootstrap_reflex_integration_for_django_mode()

    from reflex_base.config import get_config

    cfg = get_config()
    assert cfg.frontend_port == 4000
    assert any(
        type(p).__name__ == "ReflexDjangoPlugin" for p in (cfg.plugins or ())
    )
