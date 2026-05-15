"""Batteries-included Django session auth pages for Reflex."""

from __future__ import annotations

from typing import Any

__all__ = [
    "AuthSettings",
    "DjangoAuthState",
    "add_auth_pages",
    "autoload",
    "get_auth_settings",
    "pages",
    "login_required",
    "routes",
]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthSettings": ("reflex_django.auth.settings", "AuthSettings"),
    "DjangoAuthState": ("reflex_django.auth.state", "DjangoAuthState"),
    "add_auth_pages": ("reflex_django.auth.registry", "add_auth_pages"),
    "autoload": ("reflex_django.auth.registry", "autoload"),
    "get_auth_settings": ("reflex_django.auth.settings", "get_auth_settings"),
    "pages": ("reflex_django.auth.pages", None),
    "login_required": ("reflex_django.auth.decorators", "login_required"),
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
