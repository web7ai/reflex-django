"""Shared UI primitives for canned auth pages."""

from __future__ import annotations

import reflex as rx

AUTH_CARD_MAX_WIDTH = "28em"
PADDING_TOP = "4rem"


def brand_icon(*, size: int = 28) -> rx.Component:
    return rx.box(
        rx.icon("layers", size=size),
        padding="0.55rem",
        border_radius="25%",
        background=rx.color("accent", 4),
        color=rx.color("accent", 11),
        display="flex",
        align_items="center",
        justify_content="center",
    )


def branded_icon_from_settings() -> rx.Component:
    """Render brand icon/text from ``REFLEX_DJANGO_AUTH`` branding settings."""
    from reflex_django.auth.settings import get_auth_settings

    auth = get_auth_settings()
    if auth.brand_icon_src:
        return rx.image(
            src=auth.brand_icon_src,
            height="48px",
            width="auto",
            object_fit="contain",
            margin_bottom="0.25em",
        )
    if auth.brand_text:
        return rx.text(
            auth.brand_text,
            font_weight="700",
            font_size="1.25rem",
            letter_spacing="-0.02em",
            text_align="center",
            margin_bottom="0.25em",
        )
    return brand_icon()


def input_100w(name: str, **props: object) -> rx.Component:
    """Full-width text input with a ``name`` for form submission."""
    return rx.input(name=name, width="100%", size="3", **props)


def labeled_field(
    label: str,
    field: rx.Component,
    *,
    trailing: rx.Component | None = None,
) -> rx.Component:
    header = (
        rx.hstack(
            rx.text(label, size="3", weight="medium"),
            trailing,
            justify="between",
            width="100%",
        )
        if trailing is not None
        else rx.text(label, size="3", weight="medium", width="100%")
    )
    return rx.vstack(
        header,
        field,
        spacing="2",
        width="100%",
    )


def auth_card(*children: rx.Component, **props: object) -> rx.Component:
    """Centered card wrapper for auth forms."""
    return rx.card(
        rx.vstack(*children, spacing="6", width="100%"),
        size="4",
        max_width=AUTH_CARD_MAX_WIDTH,
        width="100%",
        class_name="auth-card",
        **props,
    )


def auth_page_shell(content: rx.Component) -> rx.Component:
    """Vertically centered page layout for auth screens."""
    return rx.center(
        content,
        padding_top=PADDING_TOP,
        padding_x="1rem",
        min_height="100vh",
        width="100%",
        background=rx.color("gray", 2),
    )


def error_callout(message: rx.Var | str) -> rx.Component:
    """Red callout for validation or auth errors."""
    return rx.callout(
        message,
        icon="circle-x",
        color_scheme="red",
        role="alert",
        size="2",
        width="100%",
    )


def success_callout(message: rx.Var | str) -> rx.Component:
    """Green callout for success messages."""
    return rx.callout(
        message,
        icon="circle-check",
        color_scheme="green",
        role="status",
        size="2",
        width="100%",
    )
