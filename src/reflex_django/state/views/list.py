"""Read-only list model state."""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.mixins.auth import LoginRequiredMixin
from reflex_django.state.mixins.list import ListMixin
from reflex_django.state.mixins.permission import PermissionMixin
from reflex_django.state.views.meta import ModelListMeta


class ModelListView(ListMixin, LoginRequiredMixin, PermissionMixin, ABC):
    """Load and display a serialized list only (no create/update/delete)."""

    serializer_class: ClassVar[type[ReflexDjangoModelSerializer] | None] = None
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

    class Meta(ModelListMeta):
        """Optional overrides (prefer class attributes for IDE autocomplete)."""


__all__ = ["ModelListView"]
