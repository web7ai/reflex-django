"""Minimal Reflex app factory for app_factory tests."""

from __future__ import annotations

import reflex as rx

from reflex_django.decorators import page


def create_app() -> rx.App:
    return rx.App()


@page(route="/fixture-about")
def about_page() -> rx.Component:
    return rx.text("about")
