"""Reusable Reflex :class:`reflex.state.State` building blocks for Django-backed apps."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ModelCRUDConfig",
    "SessionAuthConfig",
    "_default_row_serializer",
    "crud_mixin",
    "ReflexDjangoModelSerializer",
    "serialize_model_row",
    "session_auth_mixin",
]

_LAZY: dict[str, tuple[str, str]] = {
    "ModelCRUDConfig": ("reflex_django.mixins.crud", "ModelCRUDConfig"),
    "SessionAuthConfig": ("reflex_django.mixins.session_auth", "SessionAuthConfig"),
    "_default_row_serializer": ("reflex_django.mixins.crud", "_default_row_serializer"),
    "crud_mixin": ("reflex_django.mixins.crud", "crud_mixin"),
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
