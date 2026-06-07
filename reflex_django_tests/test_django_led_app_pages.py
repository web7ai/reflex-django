"""Tests for django_led_app.app page registration."""

from __future__ import annotations

import pytest

from reflex_django.app_factory import (
    ensure_django_led_app_ready,
    get_or_create_app,
    reset_app_factory_cache,
)
from reflex_django.mount_config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.pages.decorators import PAGE_REGISTRY, clear_page_registry


@pytest.fixture(autouse=True)
def _reset() -> None:
    clear_mount_rx_config()
    register_mount_rx_config(app_name="demo")
    reset_app_factory_cache()
    clear_page_registry()
    yield
    reset_app_factory_cache()
    clear_page_registry()
    clear_mount_rx_config()


def test_get_or_create_app_singleton() -> None:
    import reflex_django.reflex_app as reflex_app

    reflex_app._app = None
    first = get_or_create_app()
    second = get_or_create_app()
    assert first is second
    assert reflex_app.app is first


def test_add_page_on_django_led_app() -> None:
    import reflex as rx
    import reflex_django.reflex_app as reflex_app

    reflex_app._app = None
    app = reflex_app.app

    def sample_page() -> rx.Component:
        return rx.text("hello")

    app.add_page(sample_page, route="/sample-led")
    ready = ensure_django_led_app_ready()
    assert ready is app
    unevaluated = getattr(app, "_unevaluated_pages", {})
    assert "sample-led" in unevaluated or "/sample-led" in unevaluated or any(
        reg.route in ("/sample-led", "sample-led") for reg in PAGE_REGISTRY
    )


def test_lazy_app_export_matches_django_led_app() -> None:
    import reflex_django.django_led_app as django_led

    django_led._app = None
    from reflex_django import app as exported

    assert exported is django_led.app


def test_page_decorator_and_add_page_share_singleton() -> None:
    import reflex as rx
    import reflex_django.django_led_app as django_led
    from reflex_django.pages.decorators import page

    django_led._app = None
    app = django_led.app

    @page(route="/decorated", title="Decorated")
    def decorated_page() -> rx.Component:
        return rx.text("decorated")

    def added_page() -> rx.Component:
        return rx.text("added")

    app.add_page(added_page, route="/added")
    ready = ensure_django_led_app_ready()
    assert ready is app
    unevaluated = getattr(app, "_unevaluated_pages", {})
    routes = {str(k).lstrip("/") for k in unevaluated}
    assert "decorated" in routes or "added" in routes
