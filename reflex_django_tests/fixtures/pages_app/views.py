"""Fixture pages for auto-discovery tests."""

from __future__ import annotations

import reflex as rx

from reflex_django.pages.decorators.templates import centered_template as template


@template(route="/discovered-home", title="Discovered")
def discovered_home() -> rx.Component:
    return rx.text("discovered")
