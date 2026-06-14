"""Tests for app_factory and routing helpers."""

from __future__ import annotations

import pytest
from django.conf import settings

from reflex_django.runtime.app_factory import (
    create_app,
    discover_page_modules,
    import_page_packages,
    load_app_factory,
    register_reflex_app_module,
    reset_app_factory_cache,
    resolve_page_packages,
)
from reflex_django.pages.decorators import PAGE_REGISTRY, clear_page_registry
from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config


@pytest.fixture(autouse=True)
def _reset_factory() -> None:
    clear_mount_rx_config()
    register_mount_rx_config(app_name="demo")
    reset_app_factory_cache()
    clear_page_registry()
    yield
    reset_app_factory_cache()
    clear_page_registry()
    clear_mount_rx_config()


def test_import_page_packages_registers_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import reflex_django_tests.fixtures.factory_app as factory_mod

    importlib.reload(factory_mod)

    monkeypatch.setattr(
        settings,
        "RX_PAGE_PACKAGES",
        ["reflex_django_tests.fixtures.factory_app"],
        raising=False,
    )
    imported = import_page_packages()
    assert imported == ["reflex_django_tests.fixtures.factory_app"]
    assert any(p.route == "/fixture-about" for p in PAGE_REGISTRY)


def test_load_app_factory() -> None:
    app = load_app_factory()
    assert app is not None


def test_ensure_django_led_app_ready_materializes_app_module_stub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from reflex_django.runtime.app_factory import (
        _APP_MODULE_STUB_MARKER,
        ensure_django_led_app_ready,
    )

    manage = tmp_path / "manage.py"
    manage.write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )
    (tmp_path / "demo").mkdir()
    monkeypatch.chdir(tmp_path)
    register_mount_rx_config(app_name="demo")

    ensure_django_led_app_ready()

    stub = tmp_path / "demo" / "demo.py"
    assert stub.is_file()
    assert _APP_MODULE_STUB_MARKER in stub.read_text(encoding="utf-8")


def test_ensure_reflex_app_module_stub_does_not_overwrite_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from reflex_django.runtime.app_factory import ensure_reflex_app_module_stub

    package = tmp_path / "demo"
    package.mkdir()
    stub = package / "demo.py"
    custom = "# user edit\nfrom reflex_django.runtime.reflex_app import app\n"
    stub.write_text(custom, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    register_mount_rx_config(app_name="demo")

    from django.conf import settings

    monkeypatch.setattr(settings, "BASE_DIR", tmp_path, raising=False)

    ensure_reflex_app_module_stub(app_name="demo")
    ensure_reflex_app_module_stub(app_name="demo")

    assert stub.read_text(encoding="utf-8") == custom


def test_ensure_django_led_app_ready_installs_event_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import django

    django.setup()
    from reflex_django.runtime.app_factory import ensure_django_led_app_ready
    from reflex_django.bridge.django_event import DjangoEventBridge
    from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_rxconfig_from_django()
    app = ensure_django_led_app_ready()
    assert any(isinstance(m, DjangoEventBridge) for m in app._middlewares)


def test_create_app_is_exported_from_package() -> None:
    from reflex_django import create_app as exported

    assert exported is create_app


def test_discover_page_modules_skips_contrib_apps() -> None:
    assert discover_page_modules() == []


def test_discover_page_modules_finds_views_in_installed_apps(
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
    packages = discover_page_modules()
    assert "reflex_django_tests.fixtures.pages_app.views" in packages


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
    register_mount_rx_config(app_name="reflex_django_tests.fixtures.pages_app")
    packages = discover_page_modules()
    assert packages[0] == "reflex_django_tests.fixtures.pages_app.views"


def test_resolve_page_packages_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "RX_PAGE_PACKAGES",
        ["reflex_django_tests.fixtures.factory_app"],
        raising=False,
    )
    assert resolve_page_packages() == ["reflex_django_tests.fixtures.factory_app"]


def test_resolve_page_packages_legacy_single_app_when_auto_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RX_AUTO_DISCOVER_PAGES", False, raising=False)
    register_mount_rx_config(app_name="myapp")
    monkeypatch.delattr(settings, "RX_PAGE_PACKAGES", raising=False)
    assert resolve_page_packages() == ["myapp.views"]


def test_import_page_packages_auto_discovers_template_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import reflex_django_tests.fixtures.pages_app.views as views_mod

    importlib.reload(views_mod)
    monkeypatch.setattr(
        settings,
        "INSTALLED_APPS",
        [
            *settings.INSTALLED_APPS,
            "reflex_django_tests.fixtures.pages_app",
        ],
        raising=False,
    )
    monkeypatch.delattr(settings, "RX_PAGE_PACKAGES", raising=False)
    imported = import_page_packages()
    assert "reflex_django_tests.fixtures.pages_app.views" in imported
    assert any(p.route == "/discovered-home" for p in PAGE_REGISTRY)


def test_register_reflex_app_module() -> None:
    import reflex as rx

    app = rx.App()
    name = register_reflex_app_module("fixtureapp", app)
    assert name == "fixtureapp.fixtureapp"
    import sys

    assert sys.modules[name].app is app
