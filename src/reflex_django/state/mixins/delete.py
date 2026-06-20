"""Delete hooks."""

from __future__ import annotations

from django.db import models

from reflex_django.state.base import ActionContext
from reflex_django.state.mixins.list import ListMixin
from reflex_django.state.mixins.update import UpdateMixin


class DeleteMixin(ListMixin, UpdateMixin):
    """Delete instances via ORM."""

    async def perform_delete(self, ctx: ActionContext, instance: models.Model) -> None:
        await instance.adelete()

    async def handle_delete(self, ctx: ActionContext) -> None:
        opts = ctx.options
        pk = ctx.pk
        if pk is None:
            return
        setattr(self, opts.error_var, "")
        instance = await self.get_object_or_none(ctx, pk)
        if instance is None:
            return
        await self.perform_delete(ctx, instance)
        editing_id = getattr(self, opts.editing_var, -1)
        if editing_id == pk:
            self._reset_state_fields()
        # Without pagination, dropping the row in place is correct and avoids a
        # full reload; under pagination a refresh keeps the page window filled.
        if (
            opts.incremental_updates
            and not opts.paginate_by
            and self.remove_row(
                ctx,
                pk,
            )
        ):
            return
        await self.refresh_list(ctx)


__all__ = ["DeleteMixin"]
