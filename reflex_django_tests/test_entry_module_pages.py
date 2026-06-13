"""Tests for entry-module page registration (cold start, dynamic routes)."""

from __future__ import annotations

import sys
import types

import pytest
from django.conf import settings

from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.runtime.app_factory import (
    clear_entry_module_pending_pages,
    get_or_create_app,
    prepare_pages_for_compile,
    reflex_app_module_name,
    reset_app_factory_cache,
)


_APP_NAME = "entrytest"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    clear_mount_rx_config()
    register_mount_rx_config(app_name=_APP_NAME)
    reset_app_factory_cache()
    clear_entry_module_pending_pages()
    yield
    reset_app_factory_cache()
    clear_entry_module_pending_pages()
    clear_mount_rx_config()
    sys.modules.pop(reflex_app_module_name(_APP_NAME), None)
    sys.modules.pop(_APP_NAME, None)


def _wire_tmp_project(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path, raising=False)
    monkeypatch.syspath_prepend(str(tmp_path))


def _norm_routes(app) -> set[str]:
    return {str(k).lstrip("/") for k in getattr(app, "_unevaluated_pages", {})}


def test_entry_module_static_route_after_get_or_create_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        '''"""Static entry page."""
from reflex_django.runtime.reflex_app import app
import reflex as rx

def cold_static() -> rx.Component:
    return rx.text("cold")

app.add_page(cold_static, route="/cold-static", title="Cold")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    app = get_or_create_app()

    assert "cold-static" in _norm_routes(app)


def test_entry_module_dynamic_routes_register_before_static(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        '''"""Dynamic + static entry pages (static listed first in file)."""
from reflex_django.runtime.reflex_app import app
import reflex as rx

def items_index() -> rx.Component:
    return rx.text("items")

def item_detail() -> rx.Component:
    return rx.text("detail")

app.add_page(items_index, route="/items")
app.add_page(item_detail, route="/items/[slug]")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    app = get_or_create_app()
    routes = _norm_routes(app)

    assert "items" in routes
    assert any("slug" in key for key in app._unevaluated_pages)


def test_prepare_pages_for_compile_registers_entry_routes_without_reload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        '''"""Entry page via prepare path."""
from reflex_django.runtime.reflex_app import app
import reflex as rx

def prepare_page() -> rx.Component:
    return rx.text("prepare")

app.add_page(prepare_page, route="/prepare-entry")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    prepare_pages_for_compile()
    app = get_or_create_app()

    assert "prepare-entry" in _norm_routes(app)


def test_page_decorator_in_entry_module_via_prepare(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from reflex_django.runtime.integration import install_reflex_django_integration

    install_reflex_django_integration()

    package = tmp_path / _APP_NAME
    package.mkdir()
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        '''"""Entry module @page."""
from reflex_django.runtime.reflex_app import app
import reflex as rx
from reflex_django.pages.decorators import page

@page(route="/decorated-entry", title="Decorated")
def decorated_entry() -> rx.Component:
    return rx.text("decorated")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    prepare_pages_for_compile()
    app = get_or_create_app()

    assert "decorated-entry" in _norm_routes(app)


def test_second_prepare_does_not_duplicate_entry_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        '''"""Single entry route."""
from reflex_django.runtime.reflex_app import app
import reflex as rx

def once() -> rx.Component:
    return rx.text("once")

app.add_page(once, route="/once")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    prepare_pages_for_compile()
    prepare_pages_for_compile()
    app = get_or_create_app()

    assert sum(1 for k in _norm_routes(app) if k == "once") == 1
