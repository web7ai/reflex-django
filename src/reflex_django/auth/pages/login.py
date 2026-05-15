"""Canned login page."""

from __future__ import annotations

import reflex as rx

import reflex_django.auth.routes as routes
from reflex_django.auth.pages.components import (
    auth_card,
    auth_page_shell,
    error_callout,
    input_100w,
)
from reflex_django.auth.settings import get_auth_settings
from reflex_django.auth.state import DjangoAuthState


def login_page() -> rx.Component:
    """Render the login form."""
    auth = get_auth_settings()
    return auth_page_shell(
        auth_card(
            rx.heading("Sign in", size="7"),
            rx.form(
                rx.vstack(
                    rx.text("Username"),
                    input_100w("username", placeholder="Username", autocomplete="username"),
                    rx.text("Password"),
                    input_100w(
                        "password",
                        type="password",
                        placeholder="Password",
                        autocomplete="current-password",
                    ),
                    rx.cond(
                        DjangoAuthState.login_error != "",
                        error_callout(DjangoAuthState.login_error),
                        rx.fragment(),
                    ),
                    rx.button("Sign in", width="100%"),
                    rx.center(
                        rx.hstack(
                            rx.cond(
                                auth.signup_enabled,
                                rx.link(
                                    "Create account",
                                    href=routes.SIGNUP_ROUTE,
                                ),
                                rx.fragment(),
                            ),
                            rx.cond(
                                auth.password_reset_enabled,
                                rx.link(
                                    "Forgot password?",
                                    href=routes.PASSWORD_RESET_ROUTE,
                                ),
                                rx.fragment(),
                            ),
                            spacing="4",
                        ),
                        width="100%",
                    ),
                    spacing="3",
                    width="100%",
                ),
                on_submit=DjangoAuthState.submit_login_form,
                width="100%",
            ),
        ),
    )
