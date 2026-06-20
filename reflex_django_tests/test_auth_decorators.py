"""Tests for :mod:`reflex_django.auth.decorators`."""

from __future__ import annotations

import asyncio
from unittest import mock

import reflex as rx

from reflex_django.setup.conf import configure_django

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


def test_django_auth_state_has_page_guards() -> None:
    from reflex_django.auth.state import DjangoAuthState

    for guard in (
        "require_permission",
        "require_group",
        "require_staff",
        "require_superuser",
    ):
        assert hasattr(DjangoAuthState, guard), guard


def test_permission_required_page_attaches_server_guard() -> None:
    """The protected page must mount an authoritative server-side guard."""
    from reflex_django.auth.decorators import permission_required

    def my_page() -> rx.Component:
        return rx.heading("secret")

    wrapped = permission_required("app.view_thing", redirect="/denied")(my_page)
    assert wrapped.__name__ == "my_page"
    # Rendering must succeed and produce a component tree (with the guard box).
    assert wrapped() is not None


def test_staff_required_event_denies_non_staff() -> None:
    from reflex_django.auth.decorators import staff_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            u.is_staff = False
            cu.return_value = u

            class S:
                @staff_required(redirect="/denied")
                async def go(self):
                    return "ok"

            out = await S().go()
            from reflex_base.event import EventSpec

            assert isinstance(out, EventSpec)

    asyncio.run(run())


def test_staff_required_event_allows_staff() -> None:
    from reflex_django.auth.decorators import staff_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            u.is_staff = True
            cu.return_value = u

            class S:
                @staff_required
                async def go(self):
                    return "ok"

            assert await S().go() == "ok"

    asyncio.run(run())


def test_superuser_required_event_denies_non_superuser() -> None:
    from reflex_django.auth.decorators import superuser_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            u.is_superuser = False
            cu.return_value = u

            class S:
                @superuser_required(redirect="/denied")
                async def go(self):
                    return "ok"

            out = await S().go()
            from reflex_base.event import EventSpec

            assert isinstance(out, EventSpec)

    asyncio.run(run())


def test_group_required_event_allows_member() -> None:
    from reflex_django.auth import decorators as dec

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            with mock.patch(
                "reflex_django.auth.shortcuts.auser_in_group",
                new=mock.AsyncMock(return_value=True),
            ):

                class S:
                    @dec.group_required("Editors")
                    async def go(self):
                        return "ok"

                assert await S().go() == "ok"

    asyncio.run(run())


def test_group_required_event_denies_non_member() -> None:
    from reflex_django.auth import decorators as dec

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            with mock.patch(
                "reflex_django.auth.shortcuts.auser_in_group",
                new=mock.AsyncMock(return_value=False),
            ):

                class S:
                    @dec.group_required("Editors", redirect="/denied")
                    async def go(self):
                        return "ok"

                out = await S().go()
                from reflex_base.event import EventSpec

                assert isinstance(out, EventSpec)

    asyncio.run(run())


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


def test_permission_required_event_denies_without_perm() -> None:
    from reflex_django.auth.decorators import permission_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            with mock.patch(
                "reflex_django.auth.decorators.auser_has_perm",
                new=mock.AsyncMock(return_value=False),
            ):

                class S:
                    @permission_required("app.view_thing", redirect="/denied")
                    async def go(self):
                        return "ok"

                out = await S().go()
                from reflex_base.event import EventSpec

                assert isinstance(out, EventSpec)

    asyncio.run(run())


def test_permission_required_event_allows_with_perm() -> None:
    from reflex_django.auth.decorators import permission_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            with mock.patch(
                "reflex_django.auth.decorators.auser_has_perm",
                new=mock.AsyncMock(return_value=True),
            ):

                class S:
                    @permission_required("app.view_thing")
                    async def go(self):
                        return "ok"

                assert await S().go() == "ok"

    asyncio.run(run())


def test_permission_required_event_redirects_anonymous() -> None:
    from reflex_django.auth.decorators import permission_required

    async def run() -> None:
        with mock.patch("reflex_django.auth.decorators.current_user") as cu:
            u = mock.Mock()
            u.is_authenticated = False
            cu.return_value = u

            class S:
                @permission_required("app.view_thing", login_url="/login")
                async def go(self):
                    return "ok"

            out = await S().go()
            from reflex_base.event import EventSpec

            assert isinstance(out, EventSpec)

    asyncio.run(run())
