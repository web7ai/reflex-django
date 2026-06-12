"""Tests for configurable login identifiers (username / email)."""

from __future__ import annotations

import pytest
from django.conf import settings

from reflex_django.setup.conf import configure_django

configure_django()


def test_normalize_login_fields_defaults() -> None:
    from reflex_django.auth.login_fields import normalize_login_fields

    assert normalize_login_fields(None) == ("username",)
    assert normalize_login_fields(["username", "email"]) == ("username", "email")
    assert normalize_login_fields("email") == ("email",)


def test_normalize_login_fields_dedupes() -> None:
    from reflex_django.auth.login_fields import normalize_login_fields

    assert normalize_login_fields(["email", "username", "email"]) == (
        "email",
        "username",
    )


def test_normalize_login_fields_rejects_empty() -> None:
    from reflex_django.auth.login_fields import normalize_login_fields

    with pytest.raises(ValueError, match="at least one"):
        normalize_login_fields([])


def test_login_identifier_label() -> None:
    from reflex_django.auth.login_fields import login_identifier_label

    assert login_identifier_label(("username",)) == "Username"
    assert login_identifier_label(("email",)) == "Email"
    assert login_identifier_label(("username", "email")) == "Username or email"


def test_get_auth_settings_login_fields(monkeypatch) -> None:
    from reflex_django.auth.settings import get_auth_settings

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {"LOGIN_FIELDS": ["email"]},
        raising=False,
    )
    auth = get_auth_settings()
    assert auth.login_fields == ("email",)
    assert auth.messages["invalid_credentials"] == "Invalid email or password."


def test_get_auth_settings_login_fields_both_updates_message(monkeypatch) -> None:
    from reflex_django.auth.settings import get_auth_settings

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {"LOGIN_FIELDS": ["username", "email"]},
        raising=False,
    )
    auth = get_auth_settings()
    assert auth.login_fields == ("username", "email")
    assert "username" in auth.messages["invalid_credentials"].lower()
    assert "email" in auth.messages["invalid_credentials"].lower()


@pytest.mark.asyncio
async def test_aauthenticate_login_fields_username() -> None:
    from django.contrib.auth import get_user_model

    from reflex_django.auth.login_fields import aauthenticate_login_fields

    user_model = get_user_model()
    user_model.objects.create_user(
        username="loginuser",
        email="login@example.com",
        password="secret123",
    )

    class _Req:
        pass

    result = await aauthenticate_login_fields(
        _Req(),
        "loginuser",
        "secret123",
        ("username",),
    )
    assert result is not None
    assert result.username == "loginuser"


@pytest.mark.asyncio
async def test_aauthenticate_login_fields_email_only() -> None:
    from django.contrib.auth import get_user_model

    from reflex_django.auth.login_fields import aauthenticate_login_fields

    user_model = get_user_model()
    user_model.objects.create_user(
        username="emailuser",
        email="unique@example.com",
        password="secret123",
    )

    class _Req:
        pass

    by_email = await aauthenticate_login_fields(
        _Req(),
        "unique@example.com",
        "secret123",
        ("email",),
    )
    assert by_email is not None
    assert by_email.username == "emailuser"

    by_username = await aauthenticate_login_fields(
        _Req(),
        "emailuser",
        "secret123",
        ("email",),
    )
    assert by_username is None


@pytest.mark.asyncio
async def test_aauthenticate_login_fields_username_or_email() -> None:
    from django.contrib.auth import get_user_model

    from reflex_django.auth.login_fields import aauthenticate_login_fields

    user_model = get_user_model()
    user_model.objects.create_user(
        username="bothuser",
        email="both@example.com",
        password="secret123",
    )

    class _Req:
        pass

    fields = ("username", "email")
    assert (
        await aauthenticate_login_fields(_Req(), "bothuser", "secret123", fields)
    ) is not None
    assert (
        await aauthenticate_login_fields(_Req(), "both@example.com", "secret123", fields)
    ) is not None
