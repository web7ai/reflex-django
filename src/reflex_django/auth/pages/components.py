"""Shared UI primitives for canned auth pages."""

from __future__ import annotations

import reflex as rx

MIN_WIDTH = "20rem"
PADDING_TOP = "4rem"


def input_100w(name: str, **props: object) -> rx.Component:
    """Full-width text input with a ``name`` for form submission."""
    return rx.input(name=name, width="100%", **props)


def auth_card(*children: rx.Component, **props: object) -> rx.Component:
    """Centered card wrapper for auth forms."""
    return rx.card(
        rx.vstack(*children, spacing="4", width="100%", min_width=MIN_WIDTH),
        width="100%",
        max_width="24rem",
        padding="2rem",
        **props,
    )


def auth_page_shell(content: rx.Component) -> rx.Component:
    """Vertically centered page layout for auth screens."""
    return rx.center(content, padding_top=PADDING_TOP, min_height="100vh", width="100%")


def error_callout(message: rx.Var | str) -> rx.Component:
    """Red callout for validation or auth errors."""
    return rx.callout(
        message,
        icon="triangle_alert",
        color_scheme="red",
        role="alert",
        width="100%",
    )


def success_callout(message: rx.Var | str) -> rx.Component:
    """Green callout for success messages."""
    return rx.callout(
        message,
        icon="circle_check",
        color_scheme="green",
        role="status",
        width="100%",
    )
