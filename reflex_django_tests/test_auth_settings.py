"""Tests for :mod:`reflex_django.auth.settings`."""

from __future__ import annotations

from django.conf import settings

from reflex_django.conf import configure_django

configure_django()


def test_get_auth_settings_defaults() -> None:
    from reflex_django.auth.settings import get_auth_settings

    auth = get_auth_settings()
    assert auth.enabled is True
    assert auth.signup_enabled is True
    assert auth.password_reset_enabled is True
    assert auth.login_url == "/login"
    assert auth.signup_url == "/register"
    assert auth.login_fields == ("username",)
    assert "invalid_credentials" in auth.messages


def test_get_auth_settings_legacy_login_url(monkeypatch) -> None:
    from reflex_django.auth.settings import get_auth_settings

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {"LOGIN_REDIRECT_URL": "/home"},
        raising=False,
    )
    monkeypatch.setattr(settings, "REFLEX_DJANGO_LOGIN_URL", "/signin", raising=False)
    auth = get_auth_settings()
    assert auth.login_url == "/signin"
    assert auth.login_redirect_url == "/home"


def test_get_auth_settings_overrides(monkeypatch) -> None:
    from reflex_django.auth.settings import get_auth_settings

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {
            "ENABLED": False,
            "SIGNUP_ENABLED": False,
            "LOGIN_URL": "/auth/login",
            "MESSAGES": {"invalid_credentials": "Nope."},
        },
        raising=False,
    )
    auth = get_auth_settings()
    assert auth.enabled is False
    assert auth.signup_enabled is False
    assert auth.login_url == "/auth/login"
    assert auth.messages["invalid_credentials"] == "Nope."
