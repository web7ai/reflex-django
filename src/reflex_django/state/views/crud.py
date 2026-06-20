"""Batteries-included CRUD model state."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.mixins.auth import LoginRequiredMixin
from reflex_django.state.mixins.dispatch import DispatchMixin
from reflex_django.state.mixins.orm_api import ModelORMMixin
from reflex_django.state.options import ModelStateOptions
from reflex_django.state.views.meta import ModelCRUDMeta


class ModelCRUDView(ModelORMMixin, DispatchMixin, LoginRequiredMixin, ABC):
    """Declarative CRUD mixin stack (combine with :class:`~reflex_django.states.AppState`).

    Configuration (IDE-friendly — set on the subclass body, not only in ``Meta``)::

          class NotesState(AppState, ModelCRUDView):
              serializer_class = NoteSerializer
              paginate_by = 20
              search_fields = ("title", "content")

    Legacy inner ``Meta`` still works; inherit :class:`ModelCRUDMeta` for autocomplete::

          class NotesState(AppState, ModelCRUDView):
              class Meta(ModelCRUDMeta):
                  paginate_by = 20

    After the class is created, read resolved names via :meth:`get_options` or the
    ``options`` alias (e.g. ``NotesState.options.list_var``).
    """

    # --- Declarative config (ClassVar = not Reflex vars; used only at assembly) ---
    serializer_class: ClassVar[type[ReflexDjangoModelSerializer] | None] = None
    list_var: ClassVar[str | None] = None
    error_var: ClassVar[str | None] = None
    field_errors_var: ClassVar[str | None] = None
    editing_var: ClassVar[str | None] = None
    state_fields: ClassVar[tuple[str, ...] | list[str] | None] = None
    ordering: ClassVar[tuple[str, ...] | list[str] | None] = None
    required_fields: ClassVar[tuple[str, ...] | list[str] | None] = None
    read_only_fields: ClassVar[tuple[str, ...] | list[str]] = ()
    exclude_from_row: ClassVar[tuple[str, ...] | list[str]] = ()
    on_load_event: ClassVar[str | None] = None
    save_event: ClassVar[str | None] = None
    delete_event: ClassVar[str | None] = None
    cancel_event: ClassVar[str | None] = None
    login_required_actions: ClassVar[frozenset[str] | None] = None
    permission_classes: ClassVar[tuple[type, ...]] = ()
    backend_class: ClassVar[type | None] = None
    structured_errors: ClassVar[bool] = False
    # ``run_model_validation`` is Meta-only (see :class:`ModelCRUDMeta`); do not
    # declare it here — a same-named ClassVar shadows :meth:`validate_model_full_clean`.
    reset_after_save: ClassVar[bool] = True
    form_reset_var: ClassVar[str | None] = "form_reset_key"
    use_form_submit: ClassVar[bool] = False
    paginate_by: ClassVar[int | None] = None
    max_page_size: ClassVar[int] = 100
    page_var: ClassVar[str] = "page"
    page_size_var: ClassVar[str] = "page_size"
    total_count_var: ClassVar[str | None] = None
    page_count_var: ClassVar[str | None] = None
    search_fields: ClassVar[tuple[str, ...] | list[str]] = ()
    search_var: ClassVar[str | None] = None
    allow_dynamic_ordering: ClassVar[bool] = False
    ordering_var: ClassVar[str | None] = None
    queryset_select_related: ClassVar[tuple[str, ...] | list[str]] = ()
    queryset_prefetch: ClassVar[tuple[str, ...] | list[str]] = ()
    use_canonical_api: ClassVar[bool] = True
    # When True, mutations patch the affected row in the list var instead of
    # reloading the whole page. Falls back to a full refresh when a correct
    # incremental update is not possible (e.g. inserting/removing under
    # pagination). See :class:`~reflex_django.state.mixins.list.ListMixin`.
    incremental_updates: ClassVar[bool] = False

    class Meta(ModelCRUDMeta):
        """Optional overrides (prefer class attributes above for IDE autocomplete)."""

    @classmethod
    def options(cls) -> ModelStateOptions:
        """Resolved assembly options for this state class (alias for :meth:`get_options`)."""
        return cls.get_options()


__all__ = ["ModelCRUDView"]
