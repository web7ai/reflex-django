"""Canned password reset request and confirm pages."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.pages.base import BaseAuthPage
from reflex_django.auth.pages.components import input_100w
from reflex_django.auth.settings import AuthSettings
from reflex_django.auth.state import DjangoAuthState


class PasswordResetPage(BaseAuthPage):
    """Default forgot-password page. Override hook methods or :attr:`state_cls` to customize."""

    default_title = "Reset password"
    default_on_load = None
    state_cls = DjangoAuthState

    EMAIL_FIELD = "email"

    @classmethod
    def heading_text(cls) -> str:
        return cls.message("reset_heading")

    @classmethod
    def submit_label(cls) -> str:
        return cls.message("reset_submit")

    @classmethod
    def back_link_text(cls) -> str:
        return cls.message("reset_back_link")

    @classmethod
    def heading(cls) -> rx.Component:
        return rx.heading(cls.heading_text(), size="7")

    @classmethod
    def instructions(cls) -> rx.Component:
        return rx.text(cls.message("reset_instructions"))

    @classmethod
    def email_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text("Email"),
            input_100w(
                cls.EMAIL_FIELD,
                type="email",
                placeholder="Email",
                autocomplete="email",
            ),
        )

    @classmethod
    def error_display(cls) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.reset_error != "",
            cls.error_for(state.reset_error),
            rx.fragment(),
        )

    @classmethod
    def submit_button(cls) -> rx.Component:
        return rx.button(cls.submit_label(), width="100%")

    @classmethod
    def back_link(cls) -> rx.Component:
        return rx.center(
            rx.link(cls.back_link_text(), href=routes.LOGIN_ROUTE),
            width="100%",
        )

    @classmethod
    def request_form(cls) -> rx.Component:
        state = cls.get_state()
        return cls.auth_form(
            rx.vstack(
                cls.instructions(),
                cls.email_field(),
                cls.error_display(),
                cls.submit_button(),
                cls.back_link(),
                spacing="3",
                width="100%",
            ),
            on_submit=state.submit_password_reset_request,
        )

    @classmethod
    def success_view(cls, auth: AuthSettings) -> rx.Component:
        return cls.success_for(auth.messages["reset_email_sent"])

    @classmethod
    def body(cls, auth: AuthSettings) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.reset_email_sent,
            cls.success_view(auth),
            cls.request_form(),
        )

    @classmethod
    def render(cls) -> rx.Component:
        auth = cls.auth_settings()
        return cls.shell(cls.card(cls.heading(), cls.body(auth)))


class PasswordResetConfirmPage(BaseAuthPage):
    """Default set-new-password page. Override hook methods or :attr:`state_cls` to customize."""

    default_title = "Set new password"
    default_on_load = DjangoAuthState.on_load_password_reset_confirm
    state_cls = DjangoAuthState

    NEW_PASSWORD_FIELD = "new_password"
    CONFIRM_PASSWORD_FIELD = "confirm_password"

    @classmethod
    def heading_text(cls) -> str:
        return cls.message("reset_confirm_heading")

    @classmethod
    def submit_label(cls) -> str:
        return cls.message("reset_confirm_submit")

    @classmethod
    def back_link_text(cls) -> str:
        return cls.message("reset_back_link")

    @classmethod
    def heading(cls) -> rx.Component:
        return rx.heading(cls.heading_text(), size="7")

    @classmethod
    def password_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text(cls.message("reset_confirm_password_label")),
            input_100w(
                cls.NEW_PASSWORD_FIELD,
                type="password",
                placeholder="New password",
                autocomplete="new-password",
            ),
        )

    @classmethod
    def confirm_password_field(cls) -> rx.Component:
        return rx.fragment(
            rx.text(cls.message("reset_confirm_confirm_label")),
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
            state.reset_error != "",
            cls.error_for(state.reset_error),
            rx.fragment(),
        )

    @classmethod
    def submit_button(cls) -> rx.Component:
        return rx.button(cls.submit_label(), width="100%")

    @classmethod
    def back_link(cls) -> rx.Component:
        return rx.center(
            rx.link(cls.back_link_text(), href=routes.LOGIN_ROUTE),
            width="100%",
        )

    @classmethod
    def confirm_form(cls) -> rx.Component:
        state = cls.get_state()
        return cls.auth_form(
            rx.vstack(
                cls.password_field(),
                cls.confirm_password_field(),
                cls.error_display(),
                cls.submit_button(),
                cls.back_link(),
                spacing="3",
                width="100%",
            ),
            on_submit=state.submit_password_reset_confirm,
        )

    @classmethod
    def success_view(cls, auth: AuthSettings) -> rx.Component:
        return cls.success_for(auth.messages["reset_success"])

    @classmethod
    def loading_view(cls) -> rx.Component:
        return rx.center(
            rx.text(cls.message("reset_confirm_loading"), size="2", color="gray"),
            width="100%",
        )

    @classmethod
    def invalid_view(cls, auth: AuthSettings) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.reset_error != "",
            cls.error_for(state.reset_error),
            cls.error_for(auth.messages["reset_invalid_link"]),
        )

    @classmethod
    def body(cls, auth: AuthSettings) -> rx.Component:
        state = cls.get_state()
        return rx.cond(
            state.reset_success,
            cls.success_view(auth),
            rx.cond(
                state.reset_link_valid,
                cls.confirm_form(),
                rx.cond(
                    state.reset_confirm_loaded,
                    cls.invalid_view(auth),
                    cls.loading_view(),
                ),
            ),
        )

    @classmethod
    def render(cls) -> rx.Component:
        auth = cls.auth_settings()
        return cls.shell(cls.card(cls.heading(), cls.body(auth)))


password_reset_page = PasswordResetPage
password_reset_confirm_page = PasswordResetConfirmPage
