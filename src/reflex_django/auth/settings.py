"""Django-settings-driven auth configuration (allauth-style ``RX_AUTH``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from reflex_django.auth.login_fields import (
    DEFAULT_LOGIN_FIELDS,
    default_invalid_credentials_message,
    normalize_login_fields,
)


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
    # Login page labels
    "login_heading": "Sign in",
    "login_submit": "Sign in",
    "login_signup_link": "Create account",
    "login_forgot_link": "Forgot password?",
    # Register page labels
    "register_heading": "Create an account",
    "register_submit": "Sign up",
    "register_signin_link": "Sign in",
    "register_username_label": "Username",
    "register_email_label": "Email",
    "register_email_optional_label": "Email (optional)",
    "register_password_label": "Password",
    "register_confirm_password_label": "Confirm password",
    # Password reset request labels
    "reset_heading": "Reset password",
    "reset_instructions": (
        "Enter your account email and we will send reset instructions."
    ),
    "reset_submit": "Send reset link",
    "reset_back_link": "Back to sign in",
    # Password reset confirm labels
    "reset_confirm_heading": "Choose a new password",
    "reset_confirm_submit": "Update password",
    "reset_confirm_loading": "Checking reset link…",
    "reset_confirm_password_label": "New password",
    "reset_confirm_confirm_label": "Confirm password",
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
    password_reset_confirm_url: str = "/password-reset/confirm/[uid]/[key]"
    login_redirect_url: str = "/"
    logout_redirect_url: str = "/login"
    signup_redirect_url: str = "/login"
    redirect_authenticated_user: str = "/"
    email_required: bool = False
    username_min_length: int = 1
    password_min_length: int = 8
    #: Allowed login identifiers for the canned login form (``username``, ``email``, or both).
    login_fields: tuple[str, ...] = DEFAULT_LOGIN_FIELDS
    messages: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_MESSAGES))
    #: Optional brand label shown above auth form headings (replaces default icon).
    brand_text: str = ""
    #: Optional image URL for auth page branding (shown when set; overrides icon).
    brand_icon_src: str = ""
    #: Optional dotted import paths for custom auth page subclasses.
    page_classes: dict[str, str] = field(default_factory=dict)


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

    Reads ``RX_AUTH`` for auth UI and redirect configuration.

    Returns:
        Frozen settings used by canned auth pages and mixins.
    """
    from django.conf import settings

    raw = _coerce_auth_dict(getattr(settings, "RX_AUTH", None))

    login_url = str(raw.get("LOGIN_URL", "/login"))
    logout_url = str(raw.get("LOGOUT_REDIRECT_URL", login_url))
    login_fields = normalize_login_fields(raw.get("LOGIN_FIELDS", DEFAULT_LOGIN_FIELDS))
    messages = _merge_messages(raw.get("MESSAGES"))
    user_messages = raw.get("MESSAGES")
    if not isinstance(user_messages, Mapping) or "invalid_credentials" not in user_messages:
        messages["invalid_credentials"] = default_invalid_credentials_message(login_fields)

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
                "/password-reset/confirm/[uid]/[key]",
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
        login_fields=login_fields,
        messages=messages,
        brand_text=str(raw.get("BRAND_TEXT", "") or ""),
        brand_icon_src=str(raw.get("BRAND_ICON_SRC", "") or ""),
        page_classes=_coerce_page_classes(raw.get("PAGE_CLASSES")),
    )


def _coerce_page_classes(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }


__all__ = ["AuthSettings", "get_auth_settings"]
