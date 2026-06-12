"""Tests for reflex_django.conf.configure_django."""

from __future__ import annotations

import threading

import pytest
import reflex_django.setup.conf as conf_module
from reflex_django.setup.conf import configure_django, is_configured


def test_configure_django_is_idempotent() -> None:
    """Calling configure_django multiple times returns the same module."""
    first = configure_django()
    second = configure_django()
    assert first == second
    assert is_configured()


def test_configure_django_respects_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DJANGO_SETTINGS_MODULE is set, the env wins over the arg."""
    monkeypatch.setenv(
        "DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings"
    )

    result = configure_django(settings_module="some.other.module")

    assert result == "reflex_django_tests.django_settings"


def test_configure_django_returns_active_after_setup() -> None:
    """After setup, subsequent calls return the active settings unchanged."""
    active = configure_django()
    assert configure_django(settings_module="anything.else") == active


def test_configure_django_reentrant_during_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: reentrant calls from inside ``django.setup()`` must not deadlock.

    Reproduces the scenario where admin autodiscover (or any ``AppConfig.ready``
    hook) imports a module whose top-level code calls :func:`configure_django`
    again. Before the fix, this deadlocked on a non-reentrant ``Lock``; after
    the fix, the recursive call short-circuits via the ``apps.loading`` check
    and returns the active settings module immediately.
    """
    monkeypatch.setattr(conf_module, "_SETUP_DONE", False)
    monkeypatch.setattr(conf_module, "_SETUP_LOCK", threading.RLock())

    recursive_result: list[str] = []

    class _FakeApps:
        ready = False
        loading = False

    fake_apps = _FakeApps()
    monkeypatch.setattr("django.apps.apps", fake_apps)

    def fake_setup() -> None:
        fake_apps.loading = True
        try:
            recursive_result.append(
                conf_module.configure_django(settings_module="ignored.during.setup")
            )
        finally:
            fake_apps.loading = False
            fake_apps.ready = True

    monkeypatch.setattr("django.setup", fake_setup)
    monkeypatch.setenv(
        "DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings"
    )

    outer = configure_django()

    assert outer == "reflex_django_tests.django_settings"
    assert recursive_result == ["reflex_django_tests.django_settings"]
