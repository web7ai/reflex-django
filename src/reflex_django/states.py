"""Base Reflex state classes for reflex-django apps."""

from __future__ import annotations

import sys
from abc import ABC
from typing import Any

import reflex as rx
from reflex_base.vars.base import BaseStateMeta

from reflex_django.state.assembly import maybe_assemble_model_state, register_state_class

__all__ = ["AppState", "AppStateMeta"]


class AppStateMeta(BaseStateMeta):
    """Assemble :class:`~reflex_django.state.ModelCRUDView` members before Reflex builds vars."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        mixin: bool = False,
    ) -> type:
        if name != "AppState":
            maybe_assemble_model_state(
                namespace,
                bases,
                qualname=f"{namespace.get('__module__', '')}.{name}",
                state_cls_name=name,
            )
        cls = super().__new__(mcs, name, bases, namespace, mixin=mixin)
        if name != "AppState":
            register_state_class(cls)
        return cls


class AppState(rx.State, ABC, metaclass=AppStateMeta):
    """Domain or routing state.

    Subclass this for app-wide fields (navigation, feature flags, etc.).
    Do not subclass :class:`reflex_django.DjangoUserState` here — use
    :class:`~reflex_django.DjangoUserState` (or :class:`~reflex_django.DjangoAuthState`)
    Combine with :class:`~reflex_django.state.ModelCRUDView` for declarative CRUD::

        class NotesState(AppState, ModelCRUDView):
            serializer_class = NoteSerializer
    """
