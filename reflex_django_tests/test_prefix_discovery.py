"""Tests for django_prefix auto-discovery from urlpatterns."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib import admin
from django.urls import path

from reflex_django.setup.conf import configure_django
from reflex_django.mount.config import clear_mount_registration
from reflex_django.mount.registry import clear_mount_registry
from reflex_django.mount.discovery import (
    discover_django_prefixes,
    resolve_django_prefix,
)
from reflex_django.django.urls import reflex_mount


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    clear_mount_registry()
    clear_mount_registration()
    yield
    clear_mount_registry()
    clear_mount_registration()


def test_discover_django_prefixes_first_segments() -> None:
    configure_django()
    from reflex_django_tests import test_prefix_discovery_urls as urlconf

    prefixes = discover_django_prefixes(urlconf.urlpatterns)
    assert "/admin" in prefixes
    assert "/api" in prefixes
    assert "/impersonate" in prefixes
    assert "/payments" in prefixes
    assert "/dashboard" in prefixes
    assert "/rosetta" in prefixes
    assert "" not in prefixes


def test_resolve_django_prefix_explicit_override() -> None:
    assert resolve_django_prefix(("/admin", "/api")) == ("/admin", "/api")
    assert resolve_django_prefix(()) == ()
    assert resolve_django_prefix("/billing") == ("/billing",)


def test_reflex_mount_auto_detects_from_urlpatterns_arg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_django()
    patterns = [
        path("admin/", admin.site.urls),
        path("api/", admin.site.urls),
    ]
    mount = reflex_mount(urlpatterns=patterns)
    regex = mount.pattern.regex.pattern
    assert "(?!/admin$)" in regex or "admin" in regex
    assert "(?!/api$)" in regex or "api" in regex
    assert mount.name == "reflex_mount"


def test_reflex_mount_explicit_empty_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_django()
    patterns = [path("admin/", admin.site.urls)]
    mount = reflex_mount(django_prefix=(), urlpatterns=patterns)
    regex = mount.pattern.regex.pattern
    assert "(?!/admin$)" not in regex


def test_reflex_mount_explicit_prefix_overrides_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_django()
    patterns = [
        path("admin/", admin.site.urls),
        path("api/", admin.site.urls),
    ]
    mount = reflex_mount(django_prefix=("/admin",), urlpatterns=patterns)
    regex = mount.pattern.regex.pattern
    assert "(?!/admin$)" in regex or "admin" in regex
    assert "(?!/api$)" not in regex


def test_reflex_mount_auto_from_module_urlpatterns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import sys

    configure_django()
    urlconf_name = "reflex_django_tests.test_prefix_discovery_mount_urls"
    monkeypatch.setattr(settings, "ROOT_URLCONF", urlconf_name, raising=False)
    sys.modules.pop(urlconf_name, None)
    clear_mount_registration()
    urlconf = importlib.import_module(urlconf_name)
    from django.urls import clear_url_caches

    clear_url_caches()
    from reflex_django.mount.config import get_merged_mount_registration

    assert get_merged_mount_registration().django_prefix == ("/admin", "/api")
    assert len(urlconf.urlpatterns) >= 2
    mount_pattern = urlconf.urlpatterns[-1]
    regex = mount_pattern.pattern.regex.pattern
    assert "(?!/admin$)" in regex or "admin" in regex
    assert "(?!/api$)" in regex or "api" in regex


def test_discover_includes_media_in_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    configure_django()
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(settings, "MEDIA_URL", "/media/", raising=False)
    prefixes = discover_django_prefixes([path("api/", admin.site.urls)])
    assert "/media" in prefixes
