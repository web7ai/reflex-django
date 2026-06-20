"""Views imported during app ``ready()`` before admin autodiscover (regression fixture)."""

from __future__ import annotations

import reflex as rx

from reflex_django.pages.decorators import page


@page(route="/early-page/")
def early_page() -> rx.Component:
    return rx.text("early")
