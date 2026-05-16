"""Base Reflex state classes for reflex-django apps."""

from __future__ import annotations

import sys
from abc import ABC
from typing import Any

import reflex as rx
from reflex_base.vars.base import BaseStateMeta

from reflex_django.state._model_crud import maybe_inject_model_state, register_state_class

__all__ = ["AppState", "AppStateMeta"]


class AppStateMeta(BaseStateMeta):
    """Inject :class:`~reflex_django.state.ModelState` members before Reflex builds vars."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        mixin: bool = False,
    ) -> type:
        if name != "AppState":
            maybe_inject_model_state(
                namespace,
                bases,
                qualname=f"{namespace.get('__module__', '')}.{name}",
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
    for auth snapshots and mixins such as ``crud_mixin(..., base=AppState)``.

    Combine with :class:`~reflex_django.state.ModelState` for declarative CRUD::

        class NotesState(AppState, ModelState):
            class Meta:
                serializer = NoteSerializer
    """
