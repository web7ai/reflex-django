"""Tests for reflex.page bucketing under reflex_mount app_name."""

from __future__ import annotations

import reflex as rx

from reflex_django.setup.conf import configure_django

configure_django()

from reflex.page import DECORATED_PAGES  # noqa: E402
from reflex_django.pages.decorators import clear_page_registry, page
from reflex_django.runtime.integration import (
    install_reflex_django_integration,
    reset_integration_for_tests,
)
from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config


def test_patched_page_buckets_under_mount_app_name() -> None:
    clear_page_registry()
    clear_mount_rx_config()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()

    register_mount_rx_config(app_name="shop", rx_config={"app_name": "shop"})
    install_reflex_django_integration()

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    assert len(DECORATED_PAGES.get("shop", [])) == 1
    assert DECORATED_PAGES.get("", []) == []

    clear_page_registry()
    clear_mount_rx_config()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()
