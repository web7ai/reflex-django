"""Tests for Django-driven rx.Config merge."""

from __future__ import annotations

import dataclasses

import pytest
from django.conf import settings
from reflex_base.config import Config

from reflex_django.setup.rxconfig_bridge import (
    _apply_built_with_reflex_default,
    merge_rx_config,
)


def test_merge_rx_config_override() -> None:
    base = Config(app_name="file", frontend_port=3001, _skip_plugins_checks=True)
    merged = merge_rx_config(
        base,
        {"frontend_port": 3000},
        override=True,
    )
    assert merged.frontend_port == 3000
    assert merged.app_name == "file"


def test_merge_rx_config_fill_missing() -> None:
    base = Config(app_name="file", _skip_plugins_checks=True)
    merged = merge_rx_config(
        base,
        {"frontend_port": 3000},
        override=False,
    )
    assert merged.frontend_port == 3000


def test_invalid_rx_config_key_raises() -> None:
    from reflex_django.setup.rxconfig_bridge import _coerce_rx_config_dict

    with pytest.raises(ValueError, match="Unsupported"):
        _coerce_rx_config_dict({"not_a_real_config_key": 1})


def test_show_built_with_reflex_defaults_to_false() -> None:
    """The "Built with Reflex" badge is off by default in reflex-django.

    Reflex's upstream default is ``None`` (which resolves to ``True`` at
    compile time for non-paid tiers). Django-first projects almost always
    ship their own branding, so we force ``False`` unless the user opts in.
    """
    base = Config(app_name="app", _skip_plugins_checks=True)
    assert base.show_built_with_reflex is None  # upstream sentinel

    out = _apply_built_with_reflex_default(base)
    assert out.show_built_with_reflex is False


def test_show_built_with_reflex_honours_django_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting ``RX_SHOW_BUILT_WITH_REFLEX = True`` re-enables the badge."""
    monkeypatch.setattr(
        settings, "RX_SHOW_BUILT_WITH_REFLEX", True, raising=False
    )
    base = Config(app_name="app", _skip_plugins_checks=True)
    out = _apply_built_with_reflex_default(base)
    assert out.show_built_with_reflex is True


def test_show_built_with_reflex_respects_explicit_mount_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``reflex_mount(rx_config={"show_built_with_reflex": True})`` wins over the default.

    Mount-level overrides represent an explicit user intent and should not
    be quietly clobbered by reflex-django's default flip.
    """
    monkeypatch.setattr(
        "reflex_django.mount.config.get_mount_rx_config_overrides",
        lambda: {"show_built_with_reflex": True},
    )
    base = Config(
        app_name="app",
        show_built_with_reflex=True,
        _skip_plugins_checks=True,
    )
    out = _apply_built_with_reflex_default(base)
    # The bridge defers to the mount override; we must not overwrite the True.
    assert out.show_built_with_reflex is True
