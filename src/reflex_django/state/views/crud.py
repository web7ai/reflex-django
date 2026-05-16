"""Batteries-included CRUD model state."""

from __future__ import annotations

from abc import ABC

from reflex_django.state.mixins.auth import LoginRequiredMixin
from reflex_django.state.mixins.dispatch import DispatchMixin


class ModelCRUDView(DispatchMixin, LoginRequiredMixin, ABC):
    """Declarative CRUD mixin stack (combine with :class:`~reflex_django.states.AppState`).

    Example::

        class NotesState(AppState, ModelCRUDView):
            serializer_class = NoteSerializer

            class Meta:
                list_var = "notes"
    """

    class Meta:
        """Optional overrides (serializer required via ``serializer_class`` or here)."""

        serializer = None
        list_var: str | None = None
        error_var: str | None = None
        field_errors_var: str | None = None
        editing_var: str | None = None
        state_fields: tuple[str, ...] | list[str] | None = None
        ordering: tuple[str, ...] | list[str] | None = None
        required_fields: tuple[str, ...] | list[str] | None = None
        read_only_fields: tuple[str, ...] | list[str] = ()
        exclude_from_row: tuple[str, ...] | list[str] = ()
        on_load_event: str | None = None
        save_event: str | None = None
        delete_event: str | None = None
        cancel_event: str | None = None
        login_required_actions: frozenset[str] | None = None
        permission_classes: tuple[type, ...] = ()
        backend_class: type | None = None
        structured_errors: bool = False
        run_model_validation: bool = False
        load_context_processors: bool = True
        reset_after_save: bool = True
        form_reset_var: str | None = "form_reset_key"
        use_form_submit: bool = False
        queryset_select_related: tuple[str, ...] | list[str] = ()
        queryset_prefetch: tuple[str, ...] | list[str] = ()


__all__ = ["ModelCRUDView"]
