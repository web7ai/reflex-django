"""Pagination hooks for model state list loading."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from reflex_django.state.base import BaseModelState


class PaginationMixin(BaseModelState):
    """Slice querysets and expose page metadata on the state instance."""

    def get_paginate_by(self) -> int | None:
        return self.get_options().paginate_by

    def pagination_enabled(self) -> bool:
        return self.get_paginate_by() is not None

    def get_page(self) -> int:
        opts = self.get_options()
        return max(1, int(getattr(self, opts.page_var, 1)))

    def get_page_size(self) -> int:
        opts = self.get_options()
        if not self.pagination_enabled():
            return 0
        raw = getattr(self, opts.page_size_var, opts.paginate_by)
        size = int(raw) if raw is not None else int(opts.paginate_by or 1)
        return min(max(1, size), opts.max_page_size)

    def paginate_queryset(self, queryset: QuerySet[Any]) -> QuerySet[Any]:
        if not self.pagination_enabled():
            return queryset
        page = self.get_page()
        size = self.get_page_size()
        start = (page - 1) * size
        return queryset[start : start + size]

    async def get_queryset_count(self, queryset: QuerySet[Any]) -> int:
        return await queryset.acount()

    def update_pagination_meta(self, total: int) -> None:
        if not self.pagination_enabled():
            return
        opts = self.get_options()
        size = self.get_page_size()
        page_count = max(1, (total + size - 1) // size) if total else 1
        page = min(self.get_page(), page_count)
        setattr(self, opts.page_var, page)
        setattr(self, opts.total_count_var, total)
        setattr(self, opts.page_count_var, page_count)

    def reset_page(self) -> None:
        if not self.pagination_enabled():
            return
        setattr(self, self.get_options().page_var, 1)

    def on_page_change(self, page: int) -> None:
        """Hook after the page index changes (override for side effects)."""


__all__ = ["PaginationMixin"]
