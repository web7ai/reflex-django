"""Canonical ORM API methods for :class:`~reflex_django.state.generic.ModelState`."""

from __future__ import annotations

from typing import Any

from reflex_django.state.base import BaseModelState
from reflex_django.state.constants import (
    ACTION_CANCEL_EDIT,
    ACTION_DELETE,
    ACTION_LOAD_LIST,
    ACTION_SAVE,
    ACTION_START_EDIT,
)


class ModelORMMixin(BaseModelState):
    """Imperative CRUD helpers that route through :meth:`dispatch`."""

    _queryset_filter: dict[str, Any] | None = None

    async def load(self, pk: int) -> None:
        """Load one row into editable state fields."""
        await self.dispatch(ACTION_START_EDIT, pk=int(pk))

    async def save(self) -> None:
        """Create or update from current state field values."""
        await self.dispatch(ACTION_SAVE)

    async def create(self) -> None:
        """Start a new row (clear edit id) and save."""
        opts = self.get_options()
        setattr(self, opts.editing_var, -1)
        await self.dispatch(ACTION_SAVE)

    async def delete(self, pk: int | None = None) -> None:
        """Delete by primary key (defaults to :attr:`editing_id`)."""
        opts = self.get_options()
        resolved = pk
        if resolved is None:
            resolved = getattr(self, opts.editing_var, -1)
        if resolved is None or int(resolved) < 0:
            return
        await self.dispatch(ACTION_DELETE, pk=int(resolved))

    async def refresh(self) -> None:
        """Reload the list var from the database."""
        await self.dispatch(ACTION_LOAD_LIST)

    async def filter(self, **kwargs: Any) -> None:
        """Apply Django ORM ``filter(**kwargs)`` and refresh the list."""
        self._queryset_filter = dict(kwargs)
        await self.refresh()

    async def clear_filter(self) -> None:
        """Clear stored filter kwargs and refresh."""
        self._queryset_filter = None
        await self.refresh()

    async def paginate(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> None:
        """Update pagination vars (when enabled) and refresh."""
        opts = self.get_options()
        if opts.paginate_by is None:
            await self.refresh()
            return
        if page_size is not None:
            clamped = min(max(1, int(page_size)), opts.max_page_size)
            setattr(self, opts.page_size_var, clamped)
        if page is not None:
            setattr(self, opts.page_var, max(1, int(page)))
            self.on_page_change(int(page))
        await self.refresh()

    async def cancel_edit(self) -> None:
        """Reset the form to create mode."""
        await self.dispatch(ACTION_CANCEL_EDIT)

    def get_row(self, pk: int) -> dict[str, Any] | None:
        """Return a row dict from the current list var, if present."""
        opts = self.get_options()
        rows: list[dict[str, Any]] = getattr(self, opts.list_var, [])
        for row in rows:
            rid = row.get("id")
            if rid is not None and int(rid) == int(pk):
                return row
        return None


__all__ = ["ModelORMMixin"]
