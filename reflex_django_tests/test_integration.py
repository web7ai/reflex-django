"""Tests for install_reflex_django_integration and get_config patching."""

from __future__ import annotations

from unittest import mock

import pytest

from reflex_django.integration import (
    _patch_reflex_compile,
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


def test_compile_wrapper_applies_stability_after_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrapped ``reflex._compile_app`` patches ``.web`` after each compile."""
    import reflex.reflex as reflex_module

    original_compile = mock.MagicMock()
    stability_calls: list[bool] = []

    monkeypatch.setattr(reflex_module, "_reflex_django_compile_patched", False)
    monkeypatch.setattr(reflex_module, "_compile_app", original_compile)
    monkeypatch.setattr(
        "reflex_django.app_factory.prepare_pages_for_compile",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.app_factory.load_app_factory",
        mock.MagicMock(return_value=mock.MagicMock()),
    )
    monkeypatch.setattr(
        "reflex_django.compile_validate.expected_dispatch_keys_from_app",
        lambda app: set(),
    )
    monkeypatch.setattr(
        "reflex_django.compile_validate.missing_frontend_dispatchers",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "reflex_django.compile_validate.warn_if_frontend_dispatchers_out_of_sync",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "reflex_django.vite_proxy.ensure_vite_django_dev_proxy_from_config",
        lambda: False,
    )
    monkeypatch.setattr(
        "reflex_django.frontend_stability.apply_frontend_stability_after_compile",
        lambda: stability_calls.append(True) or [],
    )

    _patch_reflex_compile()
    reflex_module._compile_app(avoid_dirty_check=False)

    original_compile.assert_called_once()
    assert stability_calls == [True]
