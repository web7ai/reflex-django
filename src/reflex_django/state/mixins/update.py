"""Update and edit-mode hooks."""

from __future__ import annotations

from typing import Any

from django.db import models

from reflex_django.state.base import ActionContext, BaseModelState
from reflex_django.state.mixins.object import ObjectMixin
from reflex_django.state.mixins.state_fields import StateFieldsMixin


class UpdateMixin(ObjectMixin, StateFieldsMixin):
    """Update instances and populate state vars for editing."""

    def get_update_kwargs(self, state_data: dict[str, Any]) -> dict[str, Any]:
        return dict(state_data)

    async def perform_update(
        self,
        ctx: ActionContext,
        instance: models.Model,
        state_data: dict[str, Any],
    ) -> models.Model:
        kwargs = self.get_update_kwargs(state_data)
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await instance.asave()
        return instance

    async def populate_edit_state(
        self, ctx: ActionContext, instance: models.Model
    ) -> None:
        opts = ctx.options
        setattr(self, opts.editing_var, int(instance.pk))
        for sf in opts.state_fields:
            value = getattr(instance, sf.name, None)
            setattr(self, sf.name, sf.to_var(value))
        if opts.field_errors_var:
            setattr(self, opts.field_errors_var, {})
        # Remount bound forms so inputs reflect loaded row values (not stale DOM).
        self.bump_form_reset_key()

    async def handle_start_edit(self, ctx: ActionContext) -> None:
        opts = ctx.options
        pk = ctx.pk
        if pk is None:
            return
        setattr(self, opts.error_var, "")
        instance = await self.get_object_or_none(ctx, pk)
        if instance is None:
            setattr(self, opts.error_var, f"{opts.model.__name__} not found.")
            await self.refresh_list(ctx)
            return
        await self.populate_edit_state(ctx, instance)

    async def handle_cancel_edit(self, ctx: ActionContext) -> None:
        self._reset_state_fields()


__all__ = ["UpdateMixin"]
