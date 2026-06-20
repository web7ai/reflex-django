"""Tests for in-process Django ASGI dispatch on the Reflex backend."""

from __future__ import annotations

from unittest import mock

import pytest
from django.conf import settings
from django.urls import clear_url_caches

from reflex_django.mount.config import clear_mount_registration, register_mount
from reflex_django.runtime.app_factory import (
    ensure_reflex_app_ready,
    reset_app_factory_cache,
)
from reflex_django.setup.conf import configure_django


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    clear_mount_registration()
    register_mount(app_name="demo")
    reset_app_factory_cache()
    yield
    reset_app_factory_cache()
    clear_mount_registration()


def test_ensure_reflex_app_ready_installs_django_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reflex as rx

    app = rx.App()
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.prepare_pages_for_compile",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.load_app_factory",
        mock.MagicMock(return_value=app),
    )
    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    monkeypatch.setattr(
        "django.conf.settings.RX_PROXY_SERVER",
        "",
        raising=False,
    )
    monkeypatch.setattr(
        "django.conf.settings.ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_admin_urls",
        raising=False,
    )
    monkeypatch.setattr(
        "django.conf.settings.RX_AUTO_MOUNT",
        False,
        raising=False,
    )
    clear_url_caches()
    configure_django()

    import importlib

    importlib.import_module(settings.ROOT_URLCONF)

    result = ensure_reflex_app_ready()

    assert result is app
    assert getattr(app, "_reflex_django_dispatcher_configured", False)
    assert app.api_transformer


def test_auto_mount_prepends_admin_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from reflex_django.mount.auto import clear_auto_mount_state, maybe_auto_mount
    from reflex_django.mount.discovery import discover_django_prefixes

    clear_auto_mount_state()
    monkeypatch.setattr(
        settings,
        "ROOT_URLCONF",
        "reflex_django_tests.test_django_asgi_dispatcher_urls",
        raising=False,
    )
    monkeypatch.setattr(settings, "RX_AUTO_MOUNT", True, raising=False)

    import reflex_django_tests.test_django_asgi_dispatcher_urls as urlconf

    urlconf.urlpatterns.clear()
    clear_url_caches()

    maybe_auto_mount()

    assert "/admin" in discover_django_prefixes(urlconf.urlpatterns)
