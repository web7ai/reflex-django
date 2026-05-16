"""List loading hooks."""

from __future__ import annotations

from typing import Any

from reflex_django.state.base import ActionContext, BaseModelState
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


__all__ = ["ListMixin"]
