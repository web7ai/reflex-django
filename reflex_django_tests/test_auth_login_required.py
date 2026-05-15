"""Tests for :mod:`reflex_django.auth.decorators`."""

from __future__ import annotations

import reflex as rx

from reflex_django.conf import configure_django

configure_django()


def test_login_required_wraps_page() -> None:
    from reflex_django.auth.decorators import login_required

    def my_page() -> rx.Component:
        return rx.heading("secret")

    wrapped = login_required(my_page)
    assert wrapped.__name__ == "my_page"
    comp = wrapped()
    assert comp is not None


def test_django_auth_state_has_redirect_to_login() -> None:
    from reflex_django.auth.state import DjangoAuthState

    assert hasattr(DjangoAuthState, "redirect_to_login")
    assert hasattr(DjangoAuthState, "handle_registration")
    assert hasattr(DjangoAuthState, "submit_password_reset_request")
