"""Tests for page ``on_load`` registration in Django-first mode."""

from __future__ import annotations

import reflex as rx

from reflex_django.conf import configure_django

configure_django()

from reflex_django.app_factory import reset_app_factory_cache, sync_page_load_events  # noqa: E402
from reflex_django.pages.decorators import clear_page_registry, page
from reflex_django.states import AppState


class _LoadState(AppState):
    loaded: bool = False

    @rx.event
    async def on_load(self):
        self.loaded = True


def test_sync_page_load_events_registers_handler() -> None:
    from reflex.page import DECORATED_PAGES
    from reflex_base.config import get_config

    clear_page_registry()
    reset_app_factory_cache()
    DECORATED_PAGES.clear()

    @page(route="/load-test", on_load=_LoadState.on_load)
    def load_test_page() -> rx.Component:
        return rx.text(_LoadState.loaded)

    app = rx.App()
    sync_page_load_events(app)

    assert app._load_events.get("load-test")
    events = app._load_events["load-test"]
    assert len(events) == 1
    assert events[0].fn is _LoadState.on_load.fn

    clear_page_registry()
    reset_app_factory_cache()
    DECORATED_PAGES.clear()
    get_config(reload=True)
