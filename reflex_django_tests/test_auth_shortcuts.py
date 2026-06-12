"""Tests for reflex_django.auth.shortcuts."""

from __future__ import annotations

from unittest import mock

import pytest
from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.auth.shortcuts import (  # noqa: E402
    ReflexDjangoAuthError,
    require_login_user,
)


def test_require_login_user_raises_for_anonymous() -> None:
    with mock.patch("reflex_django.auth.shortcuts.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = False
        cu.return_value = u
        with pytest.raises(ReflexDjangoAuthError):
            require_login_user()


def test_require_login_user_returns_user() -> None:
    with mock.patch("reflex_django.auth.shortcuts.current_user") as cu:
        u = mock.Mock()
        u.is_authenticated = True
        cu.return_value = u
        assert require_login_user() is u
