"""Typed configuration for :class:`~reflex_django.state.views.crud.ModelCRUDView`."""

from __future__ import annotations

from typing import ClassVar

from reflex_django.serializers import ReflexDjangoModelSerializer


class ModelCRUDMeta:
    """Configuration for model CRUD/list assembly.

    Use either:

    1. **Class attributes** on your state (best IDE autocomplete)::

           class NotesState(ModelState):
               paginate_by = 20
               search_fields = ("title", "content")

    2. **Inner Meta** inheriting this class::

           class NotesState(ModelState):
               class Meta(ModelCRUDMeta):
                   paginate_by = 20

    Resolved values are available after import via :meth:`~reflex_django.state.base.BaseModelState.get_options`.
    """

    serializer: ClassVar[type[ReflexDjangoModelSerializer] | None] = None
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
    run_model_validation: ClassVar[bool] = False  # enables validate_model_full_clean()
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


class ModelListMeta:
    """Configuration for :class:`~reflex_django.state.views.list.ModelListView`."""

    serializer: ClassVar[type[ReflexDjangoModelSerializer] | None] = None
    list_var: ClassVar[str | None] = None
    error_var: ClassVar[str | None] = None
    ordering: ClassVar[tuple[str, ...] | list[str] | None] = None
    read_only_fields: ClassVar[tuple[str, ...] | list[str]] = ()
    exclude_from_row: ClassVar[tuple[str, ...] | list[str]] = ()
    on_load_event: ClassVar[str | None] = None
    login_required_actions: ClassVar[frozenset[str] | None] = None
    permission_classes: ClassVar[tuple[type, ...]] = ()
    backend_class: ClassVar[type | None] = None
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


__all__ = ["ModelCRUDMeta", "ModelListMeta"]
