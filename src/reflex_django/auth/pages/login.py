"""Canned login page."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.login_fields import (
    login_identifier_autocomplete,
    login_identifier_label,
    login_identifier_placeholder,
)
from reflex_django.auth.pages.base import BaseAuthPage, _LazyOnLoad
from reflex_django.auth.pages.components import brand_icon, input_100w, labeled_field
from reflex_django.auth.settings import AuthSettings


class LoginPage(BaseAuthPage):
    """Default sign-in page. Override hook methods or :attr:`state_cls` to customize."""

    default_title = "Sign in"
    default_on_load = _LazyOnLoad("on_load_login")

    USERNAME_FIELD = "username"
    PASSWORD_FIELD = "password"

    @classmethod
    def heading_text(cls) -> str:
        return cls.message("login_heading")

    @classmethod
    def submit_label(cls) -> str:
        return cls.message("login_submit")

    @classmethod
    def signup_link_text(cls) -> str:
        return cls.message("login_signup_link")

    @classmethod
    def forgot_link_text(cls) -> str:
        return cls.message("login_forgot_link")

    @classmethod
    def heading(cls) -> rx.Component:
        return rx.center(
            brand_icon(),
            rx.heading(
                cls.heading_text(),
                size="6",
                as_="h2",
                text_align="center",
                width="100%",
            ),
            direction="column",
            spacing="5",
            width="100%",
        )

    @classmethod
    def identifier_field(cls, auth: AuthSettings) -> rx.Component:
        id_label = login_identifier_label(auth.login_fields)
        id_placeholder = login_identifier_placeholder(auth.login_fields)
        id_autocomplete = login_identifier_autocomplete(auth.login_fields)
        return labeled_field(
            id_label,
            input_100w(
                cls.USERNAME_FIELD,
                placeholder=id_placeholder,
                autocomplete=id_autocomplete,
            ),
        )

    @classmethod
    def password_field(cls) -> rx.Component:
        auth = cls.auth_settings()
        return labeled_field(
            "Password",
            input_100w(
                cls.PASSWORD_FIELD,
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            ),
            trailing=rx.cond(
                auth.password_reset_enabled,
                rx.link(
                    cls.forgot_link_text(),
                    href=routes.PASSWORD_RESET_ROUTE,
                    size="3",
                ),
                rx.fragment(),
            ),
        )

    @classmethod
    def error_display(cls) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.login_error != "",
            cls.error_for(state.login_error),
            rx.fragment(),
        )

    @classmethod
    def submit_button(cls) -> rx.Component:
        return rx.button(cls.submit_label(), size="3", width="100%")

    @classmethod
    def footer_links(cls, auth: AuthSettings) -> rx.Component:
        return rx.center(
            rx.cond(
                auth.signup_enabled,
                rx.hstack(
                    rx.text("New here?", size="3"),
                    rx.link(cls.signup_link_text(), href=routes.SIGNUP_ROUTE, size="3"),
                    opacity="0.85",
                    spacing="2",
                ),
                rx.fragment(),
            ),
            width="100%",
        )

    @classmethod
    def form_fields(cls, auth: AuthSettings) -> rx.Component:
        return rx.vstack(
            cls.identifier_field(auth),
            cls.password_field(),
            cls.error_display(),
            cls.submit_button(),
            cls.footer_links(auth),
            spacing="4",
            width="100%",
        )

    @classmethod
    def form_body(cls, auth: AuthSettings) -> rx.Component:
        state = cls.get_state()
        return cls.auth_form(
            cls.form_fields(auth),
            on_submit=state.submit_login_form,
        )

    @classmethod
    def render(cls) -> rx.Component:
        auth = cls.auth_settings()
        return cls.shell(cls.card(cls.heading(), cls.form_body(auth)))


login_page = LoginPage
