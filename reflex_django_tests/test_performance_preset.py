"""Tests for RX_PERFORMANCE_PRESET lean overrides."""

from __future__ import annotations

import pytest
from django.conf import settings

from reflex_django.setup.conf import configure_django

configure_django()


def test_lean_preset_overrides_defaults_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from reflex_django.setup import default_settings as defaults
    from reflex_django.setup.performance import apply_performance_preset

    monkeypatch.setattr(settings, "RX_PERFORMANCE_PRESET", "lean", raising=False)
    monkeypatch.setattr(
        settings, "RX_AUTH_AUTO_SYNC", defaults.RX_AUTH_AUTO_SYNC, raising=False
    )
    monkeypatch.setattr(
        settings, "RX_MIRROR_MESSAGES", defaults.RX_MIRROR_MESSAGES, raising=False
    )
    monkeypatch.setattr(
        settings, "RX_MIRROR_CSRF", defaults.RX_MIRROR_CSRF, raising=False
    )
    monkeypatch.setattr(
        settings, "RX_MIRROR_LANGUAGE", defaults.RX_MIRROR_LANGUAGE, raising=False
    )

    apply_performance_preset()

    assert settings.RX_AUTH_AUTO_SYNC is False
    assert settings.RX_MIRROR_MESSAGES is False
    assert settings.RX_MIRROR_CSRF is False
    assert settings.RX_MIRROR_LANGUAGE is False


def test_lean_preset_respects_user_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    from reflex_django.setup import default_settings as defaults
    from reflex_django.setup.performance import apply_performance_preset

    monkeypatch.setattr(settings, "RX_PERFORMANCE_PRESET", "lean", raising=False)
    monkeypatch.setattr(settings, "RX_AUTH_AUTO_SYNC", False, raising=False)
    monkeypatch.setattr(
        settings, "RX_MIRROR_MESSAGES", defaults.RX_MIRROR_MESSAGES, raising=False
    )

    apply_performance_preset()

    assert settings.RX_AUTH_AUTO_SYNC is False
    assert settings.RX_MIRROR_MESSAGES is False
