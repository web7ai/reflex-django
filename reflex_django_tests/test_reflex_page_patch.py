"""Tests for reflex.page bucketing under mount app_name."""

from __future__ import annotations

import reflex as rx
import pytest
from reflex_base.config import Config

from reflex_django.setup.conf import configure_django

configure_django()

from reflex.page import DECORATED_PAGES  # noqa: E402
from reflex_django.pages.decorators import clear_page_registry, page
from reflex_django.plugins import ReflexDjangoPlugin
from reflex_django.runtime.integration import (
    install_plugin_integration,
    reset_integration_for_tests,
)
from reflex_django.mount.config import clear_mount_registration, register_mount


def test_patched_page_buckets_under_mount_app_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_page_registry()
    clear_mount_registration()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()

    register_mount(app_name="shop")
    plugin = ReflexDjangoPlugin(
        config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False}
    )
    monkeypatch.setattr(
        "reflex_base.config.get_config",
        lambda reload=False: Config(app_name="shop", plugins=[plugin], _skip_plugins_checks=True),
    )
    install_plugin_integration(plugin)

    @page(route="/", title="Home")
    def index() -> rx.Component:
        return rx.text("hi")

    assert len(DECORATED_PAGES.get("shop", [])) == 1
    assert DECORATED_PAGES.get("", []) == []

    clear_page_registry()
    clear_mount_registration()
    reset_integration_for_tests()
    DECORATED_PAGES.clear()
