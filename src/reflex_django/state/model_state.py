"""Declarative CRUD :class:`reflex.state.State` from a serializer."""

from __future__ import annotations

from abc import ABC

from reflex_django.serializers import ReflexDjangoModelSerializer


class ModelState(ABC):
    """Declarative model CRUD mixin (use with :class:`~reflex_django.states.AppState`).

    Subclass with a ``Meta`` block pointing at a
    :class:`~reflex_django.serializers.ReflexDjangoModelSerializer`. Generated
    fields and ``@rx.event`` handlers are added unless the subclass already
    defines the same name in its class body.

    Example::

        class NotesState(AppState, ModelState):
            class Meta:
                serializer = NoteSerializer
                read_only_fields = ("id", "created_at", "user")
    """

    class Meta:
        """Override on concrete subclasses."""

        serializer: type[ReflexDjangoModelSerializer] | None = None
        list_var: str | None = None
        error_var: str | None = None
        form_fields: tuple[str, ...] | list[str] | None = None
        owner_field: str | None = "user"
        ordering: tuple[str, ...] | list[str] = ("-created_at",)
        required_fields: tuple[str, ...] | list[str] | None = None
        read_only_fields: tuple[str, ...] | list[str] = ()
        exclude_from_row: tuple[str, ...] | list[str] = ()
        on_load_event: str | None = None
        save_event: str | None = None
        delete_event: str | None = None
