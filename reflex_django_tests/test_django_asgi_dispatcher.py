"""Tests for in-process Django ASGI dispatch on the Reflex backend."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import clear_url_caches

from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.runtime.app_factory import get_or_create_app, reset_app_factory_cache
from reflex_django.setup.conf import configure_django


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    clear_mount_rx_config()
    register_mount_rx_config(app_name="demo")
    reset_app_factory_cache()
    yield
    reset_app_factory_cache()
    clear_mount_rx_config()


def test_get_or_create_app_installs_django_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    app = get_or_create_app()

    assert getattr(app, "_reflex_django_dispatcher_configured", False)
    assert app.api_transformer


def test_auto_mount_prepends_admin_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.conf import settings

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
