"""Auth route constants resolved from Django settings."""

from __future__ import annotations

from reflex_django.auth.settings import get_auth_settings

_ROUTE_NAMES = {
    "LOGIN_ROUTE": "login_url",
    "SIGNUP_ROUTE": "signup_url",
    "PASSWORD_RESET_ROUTE": "password_reset_url",
    "PASSWORD_RESET_CONFIRM_ROUTE": "password_reset_confirm_url",
}


def __getattr__(name: str) -> str:
    """Resolve route constants lazily from :func:`get_auth_settings`."""
    attr = _ROUTE_NAMES.get(name)
    if attr is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    return str(getattr(get_auth_settings(), attr))


__all__ = list(_ROUTE_NAMES)
