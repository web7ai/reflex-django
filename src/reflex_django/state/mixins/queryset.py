"""Queryset hooks for model state."""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet

from reflex_django.state.base import BaseModelState


class QuerySetMixin(BaseModelState):
    """``get_queryset`` / ``filter_queryset`` / ``get_ordering`` hooks."""

    def get_queryset(self) -> QuerySet[Any]:
        opts = self.get_options()
        return opts.model.objects.all()

    def filter_queryset(self, queryset: QuerySet[Any]) -> QuerySet[Any]:
        return queryset

    def get_ordering(self) -> tuple[str, ...]:
        opts = self.get_options()
        if opts.allow_dynamic_ordering:
            raw = getattr(self, opts.ordering_var, "")
            if isinstance(raw, str) and raw.strip():
                return (raw.strip(),)
        return opts.ordering

    def get_search_query(self) -> str:
        opts = self.get_options()
        if not opts.search_fields:
            return ""
        return str(getattr(self, opts.search_var, "")).strip()

    def apply_search(self, queryset: QuerySet[Any]) -> QuerySet[Any]:
        opts = self.get_options()
        if not opts.search_fields:
            return queryset
        q = self.get_search_query()
        if not q:
            return queryset
        condition = Q()
        for field in opts.search_fields:
            condition |= Q(**{f"{field}__icontains": q})
        return queryset.filter(condition)

    def get_scoped_queryset(self) -> QuerySet[Any]:
        qs = self.get_queryset()
        opts = self.get_options()
        if opts.queryset_select_related:
            qs = qs.select_related(*opts.queryset_select_related)
        if opts.queryset_prefetch:
            qs = qs.prefetch_related(*opts.queryset_prefetch)
        qs = self.filter_queryset(qs)
        qs = self.apply_search(qs)
        return qs.order_by(*self.get_ordering())


__all__ = ["QuerySetMixin"]
