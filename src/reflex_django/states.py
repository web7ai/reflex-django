"""Base Reflex state classes for reflex-django apps."""

from __future__ import annotations

from abc import ABC
from typing import Any

from reflex_base.vars.base import BaseStateMeta

from reflex_django.auth_state import DjangoUserState
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


class AppState(DjangoUserState, ABC, metaclass=AppStateMeta):
    """Base Reflex state with Django auth, session, and optional model CRUD.

    **Handlers (server-side):** use :attr:`user` and :attr:`session` for the live
    Django objects bound by :class:`~reflex_django.middleware.DjangoEventBridge`.
    Call :meth:`login`, :meth:`logout`, :meth:`has_perm`, and :meth:`has_group`
    inside ``@rx.event`` handlers.

    **UI (reactive):** use ``is_authenticated``, ``username``, ``email``,
    ``group_names``, ``is_staff``, and ``is_superuser`` (Reflex vars). They are
    refreshed automatically when ``REFLEX_DJANGO_AUTH_AUTO_SYNC`` is enabled, or
    call :meth:`~reflex_django.auth_state.DjangoUserState.sync_from_django`.

    Combine with :class:`~reflex_django.state.ModelCRUDView` for declarative CRUD::

        class NotesState(AppState, ModelCRUDView):
            serializer_class = NoteSerializer
    """
