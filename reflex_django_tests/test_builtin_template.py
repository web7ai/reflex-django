"""Tests for built-in :func:`reflex_django.template`."""

from __future__ import annotations

import pytest

from reflex_django.decorators import PAGE_REGISTRY, clear_page_registry
from reflex_django.ui.template import template


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    clear_page_registry()
    yield
    clear_page_registry()


def test_template_registers_pages_in_registry() -> None:
    import reflex as rx

    @template(route="/test-page", title="Test")
    def test_page() -> rx.Component:
        return rx.text("hi")

    routes = [p.route for p in PAGE_REGISTRY]
    assert "/test-page" in routes


def test_template_import_from_package() -> None:
    from reflex_django import page, template as pkg_template

    assert pkg_template is template
    assert page is not None


def test_fixture_views_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")

    clear_page_registry()
    import importlib

    import reflex_django_tests.fixtures.template_views as views

    importlib.reload(views)

    routes = {p.route for p in PAGE_REGISTRY}
    assert "/fixture-home" in routes
    assert "/fixture-about" in routes
