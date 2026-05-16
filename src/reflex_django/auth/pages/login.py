"""Canned login page."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.login_fields import (
    login_identifier_autocomplete,
    login_identifier_label,
    login_identifier_placeholder,
)
from reflex_django.auth.pages.base import BaseAuthPage
from reflex_django.auth.pages.components import input_100w
from reflex_django.auth.settings import AuthSettings
from reflex_django.auth.state import DjangoAuthState


class LoginPage(BaseAuthPage):
    """Default sign-in page. Override hook methods or :attr:`state_cls` to customize."""

    default_title = "Sign in"
    default_on_load = DjangoAuthState.on_load_login
    state_cls = DjangoAuthState

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
        return rx.heading(cls.heading_text(), size="7")

    @classmethod
    def identifier_field(cls, auth: AuthSettings) -> rx.Component:
        id_label = login_identifier_label(auth.login_fields)
        id_placeholder = login_identifier_placeholder(auth.login_fields)
        id_autocomplete = login_identifier_autocomplete(auth.login_fields)
        return rx.fragment(
            rx.text(id_label),
            input_100w(
                cls.USERNAME_FIELD,
                placeholder=id_placeholder,
                autocomplete=id_autocomplete,
            ),
        )

    @classmethod
    def password_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text("Password"),
            input_100w(
                cls.PASSWORD_FIELD,
                type="password",
                placeholder="Password",
                autocomplete="current-password",
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
        return rx.button(cls.submit_label(), width="100%")

    @classmethod
    def footer_links(cls, auth: AuthSettings) -> rx.Component:
        return rx.center(
            rx.hstack(
                rx.cond(
                    auth.signup_enabled,
                    rx.link(cls.signup_link_text(), href=routes.SIGNUP_ROUTE),
                    rx.fragment(),
                ),
                rx.cond(
                    auth.password_reset_enabled,
                    rx.link(cls.forgot_link_text(), href=routes.PASSWORD_RESET_ROUTE),
                    rx.fragment(),
                ),
                spacing="4",
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
            spacing="3",
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
