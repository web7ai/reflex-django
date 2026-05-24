"""Fixture pages using built-in :func:`reflex_django.template`."""

from __future__ import annotations

import reflex as rx

from reflex_django import template


@template(route="/fixture-home", title="Fixture Home")
def fixture_home() -> rx.Component:
    return rx.text("fixture home")


@template(route="/fixture-about", title="About")
def fixture_about() -> rx.Component:
    return rx.text("fixture about")
