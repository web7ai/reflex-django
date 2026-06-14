"""Tests for settings-driven auto-mount."""

from __future__ import annotations

import importlib

import pytest
from django.conf import settings
from django.contrib import admin
from django.urls import clear_url_caches, path, resolve

from reflex_django.mount.auto import (
    clear_auto_mount_state,
    maybe_auto_mount,
)
from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.mount.registry import clear_mount_registry
from reflex_django.views.mount import ReflexMountView


@pytest.fixture(autouse=True)
def _reset_mount_state() -> None:
    clear_mount_registry()
    clear_mount_rx_config()
    clear_auto_mount_state()
    yield
    clear_mount_registry()
    clear_mount_rx_config()
    clear_auto_mount_state()


def test_maybe_auto_mount_appends_catchall(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_auto_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", True, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)
    register_mount_rx_config(app_name="demo")

    maybe_auto_mount()
    clear_url_caches()

    urlconf = importlib.import_module(urlconf_name)
    assert len(urlconf.urlpatterns) == 2
    match = resolve("/spa/route")
    assert match.func.view_class is ReflexMountView


def test_maybe_auto_mount_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_auto_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", True, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)
    register_mount_rx_config(app_name="demo")

    maybe_auto_mount()
    maybe_auto_mount()
    maybe_auto_mount()

    urlconf = importlib.import_module(urlconf_name)
    assert len(urlconf.urlpatterns) == 2


def test_maybe_auto_mount_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_auto_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", False, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)

    maybe_auto_mount()
    urlconf = importlib.import_module(urlconf_name)
    assert len(urlconf.urlpatterns) == 1


def test_manual_reflex_mount_skips_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_prefix_discovery_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", True, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)
    clear_mount_rx_config()
    clear_auto_mount_state()

    urlconf = importlib.import_module(urlconf_name)
    before = len(urlconf.urlpatterns)
    maybe_auto_mount()
    assert len(urlconf.urlpatterns) == before


def test_resolve_app_name_from_rx_config(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    from reflex_django.mount.config import resolve_app_name

    monkeypatch.setattr(
        settings,
        "RX_CONFIG",
        {"app_name": "from_settings"},
        raising=False,
    )
    clear_mount_rx_config()
    assert resolve_app_name() == "from_settings"


def test_maybe_auto_mount_infers_django_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    urlconf_name = "reflex_django_tests.test_auto_mount_prefix_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", True, raising=False)
    import sys

    sys.modules.pop(urlconf_name, None)
    register_mount_rx_config(app_name="demo")

    handle = maybe_auto_mount()
    assert handle is not None
    regex = handle.url_pattern.pattern.regex.pattern
    assert "admin" in regex
    assert "api" in regex


def test_reflex_mount_rejects_removed_app_name_kwarg() -> None:
    import django

    django.setup()
    from reflex_django.django.urls import reflex_mount

    import pytest

    with pytest.raises(TypeError, match="app_name"):
        reflex_mount(app_name="legacy")
