"""Built-in Reflex state classes for reflex-django apps.

**Note:** ``reflex_django.states`` (this package) is the public facade for
built-in State classes. ``reflex_django.state`` is the internal model-state
framework (CRUD mixins, backends, views).

This module is the canonical import location for every built-in State class::

    from reflex_django.states import (
        AppState,
        DjangoUserState,
        DjangoAuthState,
        DjangoI18nState,
        ModelState,
    )

``AppState`` and ``DjangoUserState`` are available eagerly. The Django-heavy or
dynamically built classes (``DjangoAuthState``, ``DjangoI18nState``,
``ModelState``) are resolved lazily on first attribute access to avoid circular
imports and import-time ``django.setup()`` requirements.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

from reflex_base.vars.base import BaseStateMeta

from reflex_django.auth_state import DjangoUserState
from reflex_django.state.assembly import (
    maybe_assemble_model_state,
    maybe_inject_var_setters,
    register_state_class,
)

if TYPE_CHECKING:
    from reflex_django.auth.state import DjangoAuthState
    from reflex_django.states.i18n import DjangoI18nState
    from reflex_django.state.model_state import ModelState

__all__ = [
    "AppState",
    "AppStateMeta",
    "DjangoAuthState",
    "DjangoI18nState",
    "DjangoUserState",
    "ModelState",
]

_LAZY_STATES: dict[str, tuple[str, str]] = {
    "DjangoAuthState": ("reflex_django.auth.state", "DjangoAuthState"),
    "DjangoI18nState": ("reflex_django.states.i18n", "DjangoI18nState"),
    "ModelState": ("reflex_django.state.model_state", "ModelState"),
}


def __getattr__(name: str) -> Any:
    """Resolve lazy built-in State classes on first access.

    Args:
        name: The attribute requested on the ``reflex_django.states`` module.

    Returns:
        The resolved State class.

    Raises:
        AttributeError: If ``name`` is not a known built-in State.
    """
    target = _LAZY_STATES.get(name)
    if target is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    from importlib import import_module

    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value


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
            qualname = f"{namespace.get('__module__', '')}.{name}"
            maybe_assemble_model_state(
                namespace,
                bases,
                qualname=qualname,
                state_cls_name=name,
            )
            maybe_inject_var_setters(namespace, bases, qualname=qualname)
        cls = super().__new__(mcs, name, bases, namespace, mixin=mixin)
        if name != "AppState":
            register_state_class(cls)
        return cls


class AppState(DjangoUserState, ABC, metaclass=AppStateMeta):
    """Base Reflex state with Django auth, session, and optional model CRUD.

    **Handlers (server-side):** use :attr:`request`, :attr:`user`, and
    :attr:`session` for the live Django objects bound by
    :class:`~reflex_django.bridge.event.DjangoEventBridge` on every event (for
    example ``self.request.user`` in ``on_load``). Call :meth:`login`,
    :meth:`logout`, :meth:`has_perm`, and :meth:`has_group` inside
    ``@rx.event`` handlers.

    **UI (reactive):** use ``is_authenticated``, ``username``, ``email``,
    ``group_names``, ``is_staff``, and ``is_superuser`` (Reflex vars). They are
    refreshed automatically on every event (all ``DjangoUserState`` substates,
    including :class:`~reflex_django.auth.state.DjangoAuthState`) when
    ``RX_AUTH_AUTO_SYNC`` is enabled, or call
    :meth:`~reflex_django.auth_state.DjangoUserState.sync_from_django`.

    Combine with :class:`~reflex_django.state.ModelState` for declarative CRUD::

        class NotesState(ModelState):
            model = Note
            fields = ["title", "body"]

    Legacy explicit style: ``AppState`` + :class:`~reflex_django.state.ModelCRUDView`
    + ``serializer_class``.
    """
