"""Canned password reset request and confirm pages."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.pages.components import (
    auth_card,
    auth_page_shell,
    error_callout,
    input_100w,
    success_callout,
)
from reflex_django.auth.settings import get_auth_settings
from reflex_django.auth.state import DjangoAuthState


def password_reset_page() -> rx.Component:
    """Render the forgot-password form."""
    auth = get_auth_settings()
    return auth_page_shell(
        auth_card(
            rx.heading("Reset password", size="7"),
            rx.cond(
                DjangoAuthState.reset_email_sent,
                success_callout(auth.messages["reset_email_sent"]),
                rx.form(
                    rx.vstack(
                        rx.text(
                            "Enter your account email and we will send reset instructions."
                        ),
                        rx.text("Email"),
                        input_100w(
                            "email",
                            type="email",
                            placeholder="Email",
                            autocomplete="email",
                        ),
                        rx.cond(
                            DjangoAuthState.reset_error != "",
                            error_callout(DjangoAuthState.reset_error),
                            rx.fragment(),
                        ),
                        rx.button("Send reset link", width="100%"),
                        rx.center(
                            rx.link("Back to sign in", href=routes.LOGIN_ROUTE),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=DjangoAuthState.submit_password_reset_request,
                    width="100%",
                ),
            ),
        ),
    )


def password_reset_confirm_page() -> rx.Component:
    """Render the set-new-password form (uid/token in page params)."""
    auth = get_auth_settings()
    return auth_page_shell(
        auth_card(
            rx.heading("Choose a new password", size="7"),
            rx.cond(
                DjangoAuthState.reset_success,
                success_callout(auth.messages["reset_success"]),
                rx.cond(
                    DjangoAuthState.reset_link_valid,
                    rx.form(
                        rx.vstack(
                            rx.text("New password"),
                            input_100w(
                                "new_password",
                                type="password",
                                placeholder="New password",
                                autocomplete="new-password",
                            ),
                            rx.text("Confirm password"),
                            input_100w(
                                "confirm_password",
                                type="password",
                                placeholder="Confirm password",
                                autocomplete="new-password",
                            ),
                            rx.cond(
                                DjangoAuthState.reset_error != "",
                                error_callout(DjangoAuthState.reset_error),
                                rx.fragment(),
                            ),
                            rx.button("Update password", width="100%"),
                            rx.center(
                                rx.link("Back to sign in", href=routes.LOGIN_ROUTE),
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        on_submit=DjangoAuthState.submit_password_reset_confirm,
                        width="100%",
                    ),
                    rx.cond(
                        DjangoAuthState.reset_confirm_loaded,
                        rx.cond(
                            DjangoAuthState.reset_error != "",
                            error_callout(DjangoAuthState.reset_error),
                            error_callout(auth.messages["reset_invalid_link"]),
                        ),
                        rx.center(
                            rx.text("Checking reset link…", size="2", color="gray"),
                            width="100%",
                        ),
                    ),
                ),
            ),
        ),
    )
