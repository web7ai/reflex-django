"""Tests for safe current_user / anonymous_user before apps are ready."""

from __future__ import annotations

from unittest import mock

from reflex_django.conf import configure_django

configure_django()

from reflex_django.context import (  # noqa: E402
    _StandInAnonymousUser,
    anonymous_user,
    current_user,
)


def test_anonymous_user_before_apps_ready() -> None:
    with mock.patch("reflex_django.context._django_apps_ready", return_value=False):
        user = anonymous_user()
    assert isinstance(user, _StandInAnonymousUser)
    assert user.is_authenticated is False
    assert user.get_username() == ""


def test_current_user_without_request_before_apps_ready() -> None:
    with mock.patch("reflex_django.context._django_apps_ready", return_value=False):
        with mock.patch("reflex_django.context.current_request", return_value=None):
            user = current_user()
    assert isinstance(user, _StandInAnonymousUser)


def test_request_proxy_user_does_not_import_auth_at_import_time() -> None:
    """Module-level ``request.user`` must not require a ready app registry."""
    with mock.patch("reflex_django.context._django_apps_ready", return_value=False):
        with mock.patch("reflex_django.context.current_request", return_value=None):
            from reflex_django.request import request as rd_request

            user = rd_request.user
    assert isinstance(user, _StandInAnonymousUser)
