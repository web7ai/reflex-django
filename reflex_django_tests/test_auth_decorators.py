"""Tests for :mod:`reflex_django.auth.decorators`."""

from __future__ import annotations

import asyncio
from unittest import mock

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


def test_login_required_event_redirects() -> None:
    from reflex_django.auth.decorators import login_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = False
            cu.return_value = u

            class S:
                @login_required(login_url="/login")
                async def go(self):
                    return "ok"

            out = await S().go()
            from reflex_base.event import EventSpec

            assert isinstance(out, EventSpec)

    asyncio.run(run())


def test_login_required_event_allows_authenticated() -> None:
    from reflex_django.auth.decorators import login_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u

            class S:
                @login_required
                async def go(self):
                    return "ok"

            assert await S().go() == "ok"

    asyncio.run(run())
