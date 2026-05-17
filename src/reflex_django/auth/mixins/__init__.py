"""Auth state mixins for registration and password reset."""

from __future__ import annotations

from typing import Any

__all__ = [
    "PasswordResetConfig",
    "RegistrationConfig",
    "password_reset_mixin",
    "populate_password_reset_state",
    "populate_registration_state",
    "registration_mixin",
]

_LAZY: dict[str, tuple[str, str]] = {
    "PasswordResetConfig": (
        "reflex_django.auth.mixins.password_reset",
        "PasswordResetConfig",
    ),
    "password_reset_mixin": (
        "reflex_django.auth.mixins.password_reset",
        "password_reset_mixin",
    ),
    "populate_password_reset_state": (
        "reflex_django.auth.mixins.password_reset",
        "populate_password_reset_state",
    ),
    "RegistrationConfig": (
        "reflex_django.auth.mixins.registration",
        "RegistrationConfig",
    ),
    "registration_mixin": (
        "reflex_django.auth.mixins.registration",
        "registration_mixin",
    ),
    "populate_registration_state": (
        "reflex_django.auth.mixins.registration",
        "populate_registration_state",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    from importlib import import_module

    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
