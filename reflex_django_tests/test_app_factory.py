"""Tests for app_factory and routing helpers."""

from __future__ import annotations

import pytest
from django.conf import settings

from reflex_django.runtime.app_factory import (
    create_app,
    discover_page_modules,
    import_page_packages,
    load_app_factory,
    reset_app_factory_cache,
    resolve_page_packages,
)
from reflex_django.pages.decorators import PAGE_REGISTRY, clear_page_registry
from reflex_django.mount.config import clear_mount_registration, register_mount


@pytest.fixture(autouse=True)
def _reset_factory() -> None:
    clear_mount_registration()
    reset_app_factory_cache()
    register_mount(app_name="demo")
    clear_page_registry()
    yield
    reset_app_factory_cache()
    clear_page_registry()
    clear_mount_registration()


def test_import_page_packages_registers_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import reflex_django_tests.fixtures.factory_app as factory_mod

    importlib.reload(factory_mod)

    register_mount(app_name="reflex_django_tests.fixtures.factory_app")
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory._views_module_exists",
        lambda name: name == "reflex_django_tests.fixtures.factory_app.views",
    )
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.discover_page_modules",
        lambda: ["reflex_django_tests.fixtures.factory_app"],
    )
    imported = import_page_packages()
    assert imported == ["reflex_django_tests.fixtures.factory_app"]
    assert any(p.route == "/fixture-about" for p in PAGE_REGISTRY)


def test_load_app_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    import reflex as rx

    app = rx.App()
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.load_native_reflex_app",
        lambda: app,
    )
    assert load_app_factory() is app


def test_create_app_is_exported_from_package() -> None:
    from reflex_django import create_app as exported

    assert exported is create_app


def test_discover_page_modules_skips_contrib_apps() -> None:
    assert discover_page_modules() == []


def test_discover_page_modules_returns_primary_app_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_mount(app_name="reflex_django_tests.fixtures.pages_app")
    packages = discover_page_modules()
    assert packages == ["reflex_django_tests.fixtures.pages_app.views"]


def test_discover_page_modules_does_not_scan_installed_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "INSTALLED_APPS",
        [
            *settings.INSTALLED_APPS,
            "reflex_django_tests.fixtures.pages_app",
        ],
        raising=False,
    )
    register_mount(app_name="demo")
    packages = discover_page_modules()
    assert packages == []


def test_discover_page_modules_prefers_primary_app_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "INSTALLED_APPS",
        [
            *settings.INSTALLED_APPS,
            "reflex_django_tests.fixtures.pages_app",
        ],
        raising=False,
    )
    register_mount(app_name="reflex_django_tests.fixtures.pages_app")
    packages = discover_page_modules()
    assert packages[0] == "reflex_django_tests.fixtures.pages_app.views"


def test_resolve_page_packages_uses_discover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.discover_page_modules",
        lambda: ["reflex_django_tests.fixtures.factory_app"],
    )
    assert resolve_page_packages() == ["reflex_django_tests.fixtures.factory_app"]


def test_resolve_page_packages_primary_app_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    register_mount(app_name="myapp")
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory._views_module_exists",
        lambda name: name == "myapp.views",
    )
    assert resolve_page_packages() == ["myapp.views"]


def test_import_page_packages_auto_discovers_template_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import reflex_django_tests.fixtures.pages_app.views as views_mod

    importlib.reload(views_mod)
    register_mount(app_name="reflex_django_tests.fixtures.pages_app")
    imported = import_page_packages()
    assert "reflex_django_tests.fixtures.pages_app.views" in imported
    assert any(p.route == "/discovered-home" for p in PAGE_REGISTRY)
