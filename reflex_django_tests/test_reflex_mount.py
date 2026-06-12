"""Tests for reflex_mount() and mount registry."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.test import RequestFactory
from django.urls import clear_url_caches, resolve

from reflex_django.mount.config import clear_mount_rx_config
from reflex_django.mount.registry import MOUNT_REGISTRY, clear_mount_registry
from reflex_django.django.urls import reflex_mount
from reflex_django.views.mount import ReflexMountView


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    clear_mount_registry()
    clear_mount_rx_config()
    yield
    clear_mount_registry()
    clear_mount_rx_config()


def _catchall(handle):
    if hasattr(handle, "url_pattern"):
        return handle.url_pattern
    return handle


def test_reflex_mount_default_pattern(monkeypatch: pytest.MonkeyPatch) -> None:
    import django

    django.setup()
    monkeypatch.setattr(settings, "REFLEX_DJANGO_MOUNT_PREFIX", "/", raising=False)
    patterns = reflex_mount(django_prefix=("/admin", "/api"))
    pattern = _catchall(patterns)
    regex = pattern.pattern.regex.pattern
    assert regex.startswith("^")
    assert "(?!/admin$)" in regex or "admin" in regex
    assert regex.endswith(".*$") or "(?:/.*)?$" in regex
    assert len(MOUNT_REGISTRY) == 1
    assert MOUNT_REGISTRY[0].prefix == "/"
    assert patterns.name == "reflex_mount"


def test_reflex_mount_prefix_kwargs_without_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    monkeypatch.delattr(settings, "REFLEX_DJANGO_MOUNT_PREFIX", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_DJANGO_PREFIX", raising=False)
    patterns = reflex_mount(
        mount_prefix="/",
        django_prefix=("/admin", "/api"),
    )
    pattern = _catchall(patterns)
    regex = pattern.pattern.regex.pattern
    assert "(?!/admin$)" in regex or "admin" in regex
    assert "(?!/api$)" in regex or "api" in regex
    assert patterns.name == "reflex_mount"


def test_reflex_mount_custom_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    patterns = reflex_mount(mount_prefix="/app")
    pattern = _catchall(patterns)
    assert pattern.pattern.regex.pattern == r"^/app(?:/.*)?$"
    assert MOUNT_REGISTRY[0].prefix == "/app"
    assert patterns.name == "reflex_mount"


def test_reflex_mount_resolves_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "ROOT_URLCONF",
        "reflex_django_tests.test_reflex_mount_urls",
        raising=False,
    )
    clear_url_caches()

    match = resolve("/some/spa/route")
    assert match.func.view_class is ReflexMountView
