"""Reusable Reflex :class:`reflex.state.State` building blocks for Django-backed apps."""

from __future__ import annotations

from typing import Any

__all__ = [
    "SessionAuthConfig",
    "ReflexDjangoModelSerializer",
    "serialize_model_row",
    "session_auth_mixin",
]

_LAZY: dict[str, tuple[str, str]] = {
    "SessionAuthConfig": ("reflex_django.mixins.session_auth", "SessionAuthConfig"),
    "ReflexDjangoModelSerializer": (
        "reflex_django.serializers",
        "ReflexDjangoModelSerializer",
    ),
    "serialize_model_row": ("reflex_django.serialization", "serialize_model_row"),
    "session_auth_mixin": ("reflex_django.mixins.session_auth", "session_auth_mixin"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    from importlib import import_module

    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
