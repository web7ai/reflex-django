"""Tests for Django-driven rx.Config merge."""

from __future__ import annotations

import dataclasses

import pytest
from reflex_base.config import Config

from reflex_django.plugin import ReflexDjangoPlugin
from reflex_django.rxconfig_bridge import (
    ensure_reflex_django_plugin,
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


def test_ensure_reflex_django_plugin_appends() -> None:
    base = Config(app_name="app", plugins=(), _skip_plugins_checks=True)
    merged = ensure_reflex_django_plugin(base)
    assert len(merged.plugins) == 1
    assert isinstance(merged.plugins[0], ReflexDjangoPlugin)


def test_ensure_reflex_django_plugin_no_duplicate() -> None:
    existing = ReflexDjangoPlugin()
    base = Config(app_name="app", plugins=(existing,), _skip_plugins_checks=True)
    merged = ensure_reflex_django_plugin(base)
    assert len(merged.plugins) == 1


def test_invalid_rx_config_key_raises() -> None:
    from reflex_django.rxconfig_bridge import _coerce_rx_config_dict

    with pytest.raises(ValueError, match="Unsupported"):
        _coerce_rx_config_dict({"not_a_real_config_key": 1})
