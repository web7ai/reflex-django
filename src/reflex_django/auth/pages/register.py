"""Canned registration page."""

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


def register_page() -> rx.Component:
    """Render the registration form."""
    auth = get_auth_settings()
    return auth_page_shell(
        auth_card(
                rx.heading("Create an account", size="7"),
                rx.form(
                    rx.vstack(
                        rx.text("Username"),
                        input_100w("username", placeholder="Username", autocomplete="username"),
                        rx.cond(
                            auth.email_required,
                            rx.fragment(
                                rx.text("Email"),
                                input_100w(
                                    "email",
                                    type="email",
                                    placeholder="Email",
                                    autocomplete="email",
                                ),
                            ),
                            rx.fragment(
                                rx.text("Email (optional)"),
                                input_100w(
                                    "email",
                                    type="email",
                                    placeholder="Email",
                                    autocomplete="email",
                                ),
                            ),
                        ),
                        rx.text("Password"),
                        input_100w(
                            "password",
                            type="password",
                            placeholder="Password",
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
                            DjangoAuthState.registration_error != "",
                            error_callout(DjangoAuthState.registration_error),
                            rx.fragment(),
                        ),
                        rx.button("Sign up", width="100%"),
                        rx.center(
                            rx.link("Sign in", href=routes.LOGIN_ROUTE),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    on_submit=DjangoAuthState.handle_registration,
                    width="100%",
                ),
            ),
    )
