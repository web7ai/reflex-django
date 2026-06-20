"""Create hooks."""

from __future__ import annotations

from typing import Any

from django.db import models

from reflex_django.state.base import ActionContext, BaseModelState


class CreateMixin(BaseModelState):
    """Create instances via backend or ORM."""

    def get_create_kwargs(self, state_data: dict[str, Any]) -> dict[str, Any]:
        return dict(state_data)

    async def perform_create(
        self, ctx: ActionContext, state_data: dict[str, Any]
    ) -> models.Model:
        kwargs = self.get_create_kwargs(state_data)
        return await ctx.options.model.objects.acreate(**kwargs)

    async def on_save_success(
        self,
        ctx: ActionContext,
        instance: models.Model,
    ) -> None:
        """Hook after a successful create or update (before optional field reset)."""


__all__ = ["CreateMixin"]
