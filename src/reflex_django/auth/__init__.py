"""Batteries-included Django session auth pages for Reflex."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AuthSettings",
    "DjangoAuthState",
    "ReflexDjangoAuthError",
    "add_auth_pages",
    "auser_has_perm",
    "autoload",
    "get_auth_settings",
    "login_required",
    "pages",
    "require_login_user",
    "routes",
]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthSettings": ("reflex_django.auth.settings", "AuthSettings"),
    "DjangoAuthState": ("reflex_django.auth.state", "DjangoAuthState"),
    "ReflexDjangoAuthError": ("reflex_django.auth.shortcuts", "ReflexDjangoAuthError"),
    "add_auth_pages": ("reflex_django.auth.registry", "add_auth_pages"),
    "auser_has_perm": ("reflex_django.auth.shortcuts", "auser_has_perm"),
    "autoload": ("reflex_django.auth.registry", "autoload"),
    "get_auth_settings": ("reflex_django.auth.settings", "get_auth_settings"),
    "login_required": ("reflex_django.auth.decorators", "login_required"),
    "pages": ("reflex_django.auth.pages", None),
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
