"""Batteries-included Django session auth pages for Reflex."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AuthPageMeta",
    "AuthSettings",
    "BaseAuthPage",
    "DjangoAuthState",
    "LoginPage",
    "PasswordResetConfirmPage",
    "PasswordResetPage",
    "ReflexDjangoAuthError",
    "RegisterPage",
    "add_auth_pages",
    "auser_has_perm",
    "autoload",
    "get_auth_settings",
    "login_required",
    "pages",
    "register_login_page",
    "register_password_reset_confirm_page",
    "register_password_reset_page",
    "register_register_page",
    "require_login_user",
    "routes",
]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthPageMeta": ("reflex_django.auth.pages.base", "AuthPageMeta"),
    "AuthSettings": ("reflex_django.auth.settings", "AuthSettings"),
    "BaseAuthPage": ("reflex_django.auth.pages.base", "BaseAuthPage"),
    "DjangoAuthState": ("reflex_django.auth.state", "DjangoAuthState"),
    "LoginPage": ("reflex_django.auth.pages", "LoginPage"),
    "PasswordResetConfirmPage": (
        "reflex_django.auth.pages",
        "PasswordResetConfirmPage",
    ),
    "PasswordResetPage": ("reflex_django.auth.pages", "PasswordResetPage"),
    "ReflexDjangoAuthError": ("reflex_django.auth.shortcuts", "ReflexDjangoAuthError"),
    "RegisterPage": ("reflex_django.auth.pages", "RegisterPage"),
    "add_auth_pages": ("reflex_django.auth.registry", "add_auth_pages"),
    "auser_has_perm": ("reflex_django.auth.shortcuts", "auser_has_perm"),
    "autoload": ("reflex_django.auth.registry", "autoload"),
    "get_auth_settings": ("reflex_django.auth.settings", "get_auth_settings"),
    "login_required": ("reflex_django.auth.decorators", "login_required"),
    "pages": ("reflex_django.auth.pages", None),
    "register_login_page": ("reflex_django.auth.registry", "register_login_page"),
    "register_password_reset_confirm_page": (
        "reflex_django.auth.registry",
        "register_password_reset_confirm_page",
    ),
    "register_password_reset_page": (
        "reflex_django.auth.registry",
        "register_password_reset_page",
    ),
    "register_register_page": (
        "reflex_django.auth.registry",
        "register_register_page",
    ),
    "require_login_user": ("reflex_django.auth.shortcuts", "require_login_user"),
    "routes": ("reflex_django.auth.routes", None),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    from importlib import import_module

    module = import_module(target[0])
    if target[1] is None:
        value = module
    else:
        value = getattr(module, target[1])
    globals()[name] = value
    return value
