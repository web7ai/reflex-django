"""Canned registration page."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.pages.base import BaseAuthPage
from reflex_django.auth.pages.components import input_100w
from reflex_django.auth.settings import AuthSettings
from reflex_django.auth.state import DjangoAuthState


class RegisterPage(BaseAuthPage):
    """Default registration page. Override hook methods or :attr:`state_cls` to customize."""

    default_title = "Create account"
    default_on_load = DjangoAuthState.on_load_register
    state_cls = DjangoAuthState

    USERNAME_FIELD = "username"
    EMAIL_FIELD = "email"
    PASSWORD_FIELD = "password"
    CONFIRM_PASSWORD_FIELD = "confirm_password"

    @classmethod
    def heading_text(cls) -> str:
        return cls.message("register_heading")

    @classmethod
    def submit_label(cls) -> str:
        return cls.message("register_submit")

    @classmethod
    def signin_link_text(cls) -> str:
        return cls.message("register_signin_link")

    @classmethod
    def heading(cls) -> rx.Component:
        return rx.heading(cls.heading_text(), size="7")

    @classmethod
    def username_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text(cls.message("register_username_label")),
            input_100w(
                cls.USERNAME_FIELD,
                placeholder="Username",
                autocomplete="username",
            ),
        )

    @classmethod
    def email_field(cls, auth: AuthSettings) -> rx.Component:
        if auth.email_required:
            return rx.fragment(
                rx.text(cls.message("register_email_label")),
                input_100w(
                    cls.EMAIL_FIELD,
                    type="email",
                    placeholder="Email",
                    autocomplete="email",
                ),
            )
        return rx.fragment(
            rx.text(cls.message("register_email_optional_label")),
            input_100w(
                cls.EMAIL_FIELD,
                type="email",
                placeholder="Email",
                autocomplete="email",
            ),
        )

    @classmethod
    def password_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text(cls.message("register_password_label")),
            input_100w(
                cls.PASSWORD_FIELD,
                type="password",
                placeholder="Password",
                autocomplete="new-password",
            ),
        )

    @classmethod
    def confirm_password_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text(cls.message("register_confirm_password_label")),
            input_100w(
                cls.CONFIRM_PASSWORD_FIELD,
                type="password",
                placeholder="Confirm password",
                autocomplete="new-password",
            ),
        )

    @classmethod
    def error_display(cls) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.registration_error != "",
            cls.error_for(state.registration_error),
            rx.fragment(),
        )

    @classmethod
    def submit_button(cls) -> rx.Component:
        return rx.button(cls.submit_label(), width="100%")

    @classmethod
    def footer_links(cls) -> rx.Component:
        return rx.center(
            rx.link(cls.signin_link_text(), href=routes.LOGIN_ROUTE),
            width="100%",
        )

    @classmethod
    def form_fields(cls, auth: AuthSettings) -> rx.Component:
        return rx.vstack(
            cls.username_field(),
            cls.email_field(auth),
            cls.password_field(),
            cls.confirm_password_field(),
            cls.error_display(),
            cls.submit_button(),
            cls.footer_links(),
            spacing="3",
            width="100%",
        )

    @classmethod
    def form_body(cls, auth: AuthSettings) -> rx.Component:
        state = cls.get_state()
        return cls.auth_form(
            cls.form_fields(auth),
            on_submit=state.handle_registration,
        )

    @classmethod
    def render(cls) -> rx.Component:
        auth = cls.auth_settings()
        return cls.shell(cls.card(cls.heading(), cls.form_body(auth)))


register_page = RegisterPage
