"""List loading hooks."""

from __future__ import annotations

from typing import Any

from reflex_django.state.base import ActionContext
from reflex_django.state.mixins.serialize import SerializeMixin


class ListMixin(SerializeMixin):
    """Load and refresh list vars."""

    async def load_list(self, ctx: ActionContext) -> None:
        opts = ctx.options
        setattr(self, opts.error_var, "")
        rows = await ctx.backend.list_rows(ctx)
        setattr(self, opts.list_var, rows)

    async def refresh_list(self, ctx: ActionContext) -> None:
        await self.load_list(ctx)

    def _bump_total_count(self, opts: Any, delta: int) -> None:
        var = opts.total_count_var
        if var and hasattr(self, var):
            current = getattr(self, var, 0) or 0
            setattr(self, var, max(0, int(current) + delta))

    def patch_list_row(
        self,
        opts: Any,
        row: dict[str, Any],
        *,
        was_create: bool,
    ) -> bool:
        """Patch the list var with a serialized *row* (options-driven, no ctx).

        Shared by the CRUD save path and live updates. Returns ``True`` when the
        list var was updated; ``False`` when a correct incremental update is not
        possible (insert under pagination, or update of an off-page row).
        """
        rid = row.get("id")
        rows = list(getattr(self, opts.list_var, []) or [])
        for index, existing in enumerate(rows):
            if existing.get("id") == rid:
                rows[index] = row
                setattr(self, opts.list_var, rows)
                return True
        if not was_create:
            return False
        if opts.paginate_by:
            return False
        if opts.ordering and str(opts.ordering[0]).startswith("-"):
            rows.insert(0, row)
        else:
            rows.append(row)
        setattr(self, opts.list_var, rows)
        self._bump_total_count(opts, +1)
        return True

    def remove_list_row(self, opts: Any, pk: int) -> bool:
        """Remove a row by primary key from the list var (options-driven)."""
        rows = list(getattr(self, opts.list_var, []) or [])
        remaining = [r for r in rows if r.get("id") != pk]
        if len(remaining) == len(rows):
            return False
        setattr(self, opts.list_var, remaining)
        self._bump_total_count(opts, -1)
        return True

    async def apply_saved_row(
        self,
        ctx: ActionContext,
        instance: Any,
        *,
        was_create: bool,
    ) -> bool:
        """Patch the list var with a saved instance instead of reloading.

        Returns ``True`` when the list var was updated in place. Returns
        ``False`` (so the caller can fall back to a full refresh) when a
        correct incremental update is not possible — e.g. inserting a new row
        while pagination is active, or updating a row that is not on the
        current page.
        """
        row = await self.serialize_instance(ctx, instance)
        return self.patch_list_row(ctx.options, row, was_create=was_create)

    def remove_row(self, ctx: ActionContext, pk: int) -> bool:
        """Remove a row by primary key from the list var.

        Returns ``True`` when a row was removed; ``False`` when the pk was not
        present in the current list var.
        """
        return self.remove_list_row(ctx.options, pk)


__all__ = ["ListMixin"]
