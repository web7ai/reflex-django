"""Django ORM backend using state mixin hooks."""

from __future__ import annotations

from typing import Any

from django.db import models

from reflex_django.state.base import ActionContext


class DjangoORMBackend:
    """Default backend: queryset hooks + async ORM."""

    def __init__(self, state: Any) -> None:
        self.state = state

    async def list_rows(self, ctx: ActionContext) -> list[dict[str, Any]]:
        return await self.state.serialize_queryset(ctx)

    async def retrieve(self, ctx: ActionContext, pk: int) -> models.Model:
        return await self.state.get_object(ctx, pk)

    async def create(self, ctx: ActionContext, data: dict[str, Any]) -> models.Model:
        return await self.state.perform_create(ctx, data)

    async def update(
        self,
        ctx: ActionContext,
        instance: models.Model,
        data: dict[str, Any],
    ) -> models.Model:
        return await self.state.perform_update(ctx, instance, data)

    async def delete(self, ctx: ActionContext, instance: models.Model) -> None:
        await self.state.perform_delete(ctx, instance)


__all__ = ["DjangoORMBackend"]
