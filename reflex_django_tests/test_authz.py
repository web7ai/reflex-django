"""Tests for reflex_django.authz."""

from __future__ import annotations

from unittest import mock

import pytest
from reflex_django.conf import configure_django

configure_django()

from reflex_django.authz import (  # noqa: E402
    ReflexDjangoAuthError,
    django_login_required,
    require_login_user,
)


def test_require_login_user_raises_for_anonymous() -> None:
    with mock.patch("reflex_django.authz.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = False
        cu.return_value = u
        with pytest.raises(ReflexDjangoAuthError):
            require_login_user()


def test_require_login_user_returns_user() -> None:
    with mock.patch("reflex_django.authz.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = True
        cu.return_value = u
        assert require_login_user() is u


@pytest.mark.asyncio
async def test_django_login_required_redirects() -> None:
    with mock.patch("reflex_django.authz.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = False
        cu.return_value = u

        class S:
            @django_login_required(redirect_to="/login")
            async def go(self):
                return "ok"

        out = await S().go()
        from reflex_base.event import EventSpec

        assert isinstance(out, EventSpec)


@pytest.mark.asyncio
async def test_django_login_required_allows_authenticated() -> None:
    with mock.patch("reflex_django.authz.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = True
        cu.return_value = u

        class S:
            @django_login_required()
            async def go(self):
                return "ok"

        assert await S().go() == "ok"
