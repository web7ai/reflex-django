"""Tests for DECORATED_PAGES app_name migration."""

from __future__ import annotations

import pytest
import reflex as rx
from reflex_base.config import Config

from reflex_django.setup.conf import configure_django

configure_django()

from reflex.page import DECORATED_PAGES  # noqa: E402
from reflex_django.runtime.app_factory import (  # noqa: E402
    migrate_decorated_pages_app_name,
    reset_app_factory_cache,
)
from reflex_django.pages.decorators import clear_page_registry, page
from reflex_django.mount.config import clear_mount_registration, register_mount
from reflex_django.runtime.integration import (
    install_plugin_integration,
    reset_integration_for_tests,
)
from reflex_django.plugins import ReflexDjangoPlugin


@pytest.fixture
def shop_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda reload=False: Config(app_name="shop", _skip_plugins_checks=True),
    )


def test_migrate_decorated_pages_moves_empty_key_to_mount_app_name(
    shop_config: None,
) -> None:
    clear_page_registry()
    clear_mount_registration()
    reset_app_factory_cache()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()

    register_mount(app_name="shop")
    install_plugin_integration(
        ReflexDjangoPlugin(
            config={
                "settings_module": "reflex_django_tests.django_settings",
                "auto_mount": False,
            }
        )
    )

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    assert len(DECORATED_PAGES.get("shop", [])) == 1

    DECORATED_PAGES["orphan"] = DECORATED_PAGES.pop("shop")
    migrate_decorated_pages_app_name("shop")

    assert DECORATED_PAGES.get("orphan", []) == []
    assert len(DECORATED_PAGES.get("shop", [])) == 1


def test_migrate_decorated_pages_dedupes_same_route(shop_config: None) -> None:
    clear_page_registry()
    clear_mount_registration()
    reset_app_factory_cache()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()

    register_mount(app_name="shop")
    install_plugin_integration(
        ReflexDjangoPlugin(
            config={
                "settings_module": "reflex_django_tests.django_settings",
                "auto_mount": False,
            }
        )
    )

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    DECORATED_PAGES[""].append(DECORATED_PAGES["shop"].pop())
    migrate_decorated_pages_app_name("shop")

    assert len(DECORATED_PAGES.get("shop", [])) == 1

    clear_page_registry()
    clear_mount_registration()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()
