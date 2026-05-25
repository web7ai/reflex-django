"""Tests for DECORATED_PAGES app_name migration in Django-first mode."""

from __future__ import annotations

import reflex as rx

from reflex_django.conf import configure_django

configure_django()

from reflex.page import DECORATED_PAGES  # noqa: E402
from reflex_django.app_factory import (  # noqa: E402
    migrate_decorated_pages_app_name,
    reset_app_factory_cache,
)
from reflex_django.decorators import clear_page_registry, page
from reflex_django.mount_config import clear_mount_rx_config, register_mount_rx_config


def test_migrate_decorated_pages_moves_empty_key_to_mount_app_name() -> None:
    clear_page_registry()
    clear_mount_rx_config()
    reset_app_factory_cache()
    DECORATED_PAGES.clear()

    register_mount_rx_config(app_name="shop", rx_config={"app_name": "shop"})

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    assert len(DECORATED_PAGES.get("shop", [])) == 1

    DECORATED_PAGES["orphan"] = DECORATED_PAGES.pop("shop")
    migrate_decorated_pages_app_name("shop")

    assert DECORATED_PAGES.get("orphan", []) == []
    assert len(DECORATED_PAGES.get("shop", [])) == 1


def test_migrate_decorated_pages_dedupes_same_route() -> None:
    clear_page_registry()
    clear_mount_rx_config()
    reset_app_factory_cache()
    DECORATED_PAGES.clear()

    register_mount_rx_config(app_name="shop", rx_config={"app_name": "shop"})

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    DECORATED_PAGES[""].append(DECORATED_PAGES["shop"].pop())
    migrate_decorated_pages_app_name("shop")

    assert len(DECORATED_PAGES.get("shop", [])) == 1

    clear_page_registry()
    clear_mount_rx_config()
    DECORATED_PAGES.clear()
