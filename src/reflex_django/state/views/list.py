"""Read-only list model state."""

from __future__ import annotations

from abc import ABC

from reflex_django.state.mixins.auth import LoginRequiredMixin
from reflex_django.state.mixins.list import ListMixin
from reflex_django.state.mixins.permission import PermissionMixin


class ModelListView(ListMixin, LoginRequiredMixin, PermissionMixin, ABC):
    """Load and display a serialized list only (no create/update/delete)."""

    class Meta:
        serializer = None
        list_var: str | None = None
        error_var: str | None = None
        ordering: tuple[str, ...] | list[str] | None = None
        read_only_fields: tuple[str, ...] | list[str] = ()
        exclude_from_row: tuple[str, ...] | list[str] = ()
        on_load_event: str | None = None
        login_required_actions: frozenset[str] | None = None
        permission_classes: tuple[type, ...] = ()
        backend_class: type | None = None
        load_context_processors: bool = True
        queryset_select_related: tuple[str, ...] | list[str] = ()
        queryset_prefetch: tuple[str, ...] | list[str] = ()


__all__ = ["ModelListView"]
