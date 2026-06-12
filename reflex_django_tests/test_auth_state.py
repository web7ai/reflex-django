"""Tests for reflex_django.states.auth."""

from __future__ import annotations

from unittest import mock

from reflex_django.setup.conf import configure_django

configure_django()

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from reflex_django.states.auth import user_snapshot  # noqa: E402


def test_user_snapshot_anonymous() -> None:
    snap = user_snapshot(AnonymousUser())
    assert snap["is_authenticated"] is False
    assert snap["username"] == ""
    assert snap["id"] is None
    assert snap["group_names"] == []


def test_user_snapshot_authenticated() -> None:
    user = mock.Mock()
    user.is_authenticated = True
    user.pk = 7
    user.get_username = mock.Mock(return_value="alice")
    user.email = "a@example.com"
    user.first_name = "Al"
    user.last_name = "Ice"
    user.is_staff = True
    user.is_superuser = False
    snap = user_snapshot(user)
    assert snap["is_authenticated"] is True
    assert snap["username"] == "alice"
    assert snap["id"] == 7
    assert snap["email"] == "a@example.com"
    assert snap["first_name"] == "Al"
    assert snap["last_name"] == "Ice"
    assert snap["is_staff"] is True
    assert snap["group_names"] == []


def test_user_snapshot_with_groups() -> None:
    user = mock.Mock()
    user.is_authenticated = True
    user.pk = 1
    user.get_username = mock.Mock(return_value="bob")
    user.email = ""
    user.first_name = ""
    user.last_name = ""
    user.is_staff = False
    user.is_superuser = False
    snap = user_snapshot(user, group_names=["editors", "staff"])
    assert snap["group_names"] == ["editors", "staff"]
