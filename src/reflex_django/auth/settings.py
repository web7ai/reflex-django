"""Django-settings-driven auth configuration (allauth-style ``REFLEX_DJANGO_AUTH``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


_DEFAULT_MESSAGES: dict[str, str] = {
    "invalid_credentials": "Invalid username or password.",
    "username_taken": "That username is already taken.",
    "email_taken": "That email is already registered.",
    "password_mismatch": "Passwords do not match.",
    "password_too_short": "Password is too short.",
    "username_required": "Username is required.",
    "email_required": "Email is required.",
    "reset_email_sent": (
        "If an account exists for that address, you will receive reset instructions."
    ),
    "reset_success": "Your password has been set. You can sign in now.",
    "reset_invalid_link": "This reset link is invalid or has expired.",
    "registration_success": "Account created successfully.",
}


@dataclass(frozen=True)
class AuthSettings:
    """Resolved auth UI and behavior settings."""

    enabled: bool = True
    signup_enabled: bool = True
    password_reset_enabled: bool = True
    login_url: str = "/login"
    signup_url: str = "/register"
    password_reset_url: str = "/password-reset"
    password_reset_confirm_url: str = "/password-reset/confirm/[uid]/[token]"
    login_redirect_url: str = "/"
    logout_redirect_url: str = "/login"
    signup_redirect_url: str = "/login"
    redirect_authenticated_user: str = "/"
    email_required: bool = False
    username_min_length: int = 1
    password_min_length: int = 8
    messages: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_MESSAGES))


def _coerce_auth_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _merge_messages(overrides: Any) -> dict[str, str]:
    merged = dict(_DEFAULT_MESSAGES)
    if isinstance(overrides, Mapping):
        for key, value in overrides.items():
            if isinstance(key, str) and isinstance(value, str):
                merged[key] = value
    return merged


def get_auth_settings() -> AuthSettings:
    """Load :class:`AuthSettings` from ``django.conf.settings``.

    Reads ``REFLEX_DJANGO_AUTH`` and merges legacy ``REFLEX_DJANGO_LOGIN_URL`` when
    ``LOGIN_URL`` is not set in the auth dict.

    Returns:
        Frozen settings used by canned auth pages and mixins.
    """
    from django.conf import settings

    raw = _coerce_auth_dict(getattr(settings, "REFLEX_DJANGO_AUTH", None))
    legacy_login = str(getattr(settings, "REFLEX_DJANGO_LOGIN_URL", "/login"))

    login_url = str(raw.get("LOGIN_URL", legacy_login))
    logout_url = str(raw.get("LOGOUT_REDIRECT_URL", login_url))

    return AuthSettings(
        enabled=bool(raw.get("ENABLED", True)),
        signup_enabled=bool(raw.get("SIGNUP_ENABLED", True)),
        password_reset_enabled=bool(raw.get("PASSWORD_RESET_ENABLED", True)),
        login_url=login_url,
        signup_url=str(raw.get("SIGNUP_URL", "/register")),
        password_reset_url=str(raw.get("PASSWORD_RESET_URL", "/password-reset")),
        password_reset_confirm_url=str(
            raw.get(
                "PASSWORD_RESET_CONFIRM_URL",
                "/password-reset/confirm/[uid]/[token]",
            )
        ),
        login_redirect_url=str(raw.get("LOGIN_REDIRECT_URL", "/")),
        logout_redirect_url=logout_url,
        signup_redirect_url=str(raw.get("SIGNUP_REDIRECT_URL", login_url)),
        redirect_authenticated_user=str(
            raw.get("REDIRECT_AUTHENTICATED_USER", raw.get("LOGIN_REDIRECT_URL", "/"))
        ),
        email_required=bool(raw.get("EMAIL_REQUIRED", False)),
        username_min_length=int(raw.get("USERNAME_MIN_LENGTH", 1)),
        password_min_length=int(raw.get("PASSWORD_MIN_LENGTH", 8)),
        messages=_merge_messages(raw.get("MESSAGES")),
    )


__all__ = ["AuthSettings", "get_auth_settings"]
