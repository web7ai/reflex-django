"""Queryset hooks for model state."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from reflex_django.state.base import ActionContext, BaseModelState


class QuerySetMixin(BaseModelState):
    """``get_queryset`` / ``filter_queryset`` / ``get_ordering`` hooks."""

    def get_queryset(self) -> QuerySet[Any]:
        opts = self.get_options()
        return opts.model.objects.all()

    def filter_queryset(self, queryset: QuerySet[Any]) -> QuerySet[Any]:
        return queryset

    def get_ordering(self) -> tuple[str, ...]:
        return self.get_options().ordering

    def get_scoped_queryset(self) -> QuerySet[Any]:
        qs = self.get_queryset()
        opts = self.get_options()
        if opts.queryset_select_related:
            qs = qs.select_related(*opts.queryset_select_related)
        if opts.queryset_prefetch:
            qs = qs.prefetch_related(*opts.queryset_prefetch)
        qs = self.filter_queryset(qs)
        return qs.order_by(*self.get_ordering())


__all__ = ["QuerySetMixin"]
