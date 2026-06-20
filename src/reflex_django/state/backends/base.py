"""Backend protocol for model state CRUD."""

from __future__ import annotations

from typing import Any, Protocol

from django.db import models

from reflex_django.state.base import ActionContext


class StateBackend(Protocol):
    """Persistence layer for :class:`~reflex_django.state.views.crud.ModelCRUDView`."""

    def __init__(self, state: Any) -> None: ...

    async def list_rows(self, ctx: ActionContext) -> list[dict[str, Any]]: ...

    async def retrieve(self, ctx: ActionContext, pk: int) -> models.Model: ...

    async def create(
        self, ctx: ActionContext, data: dict[str, Any]
    ) -> models.Model: ...

    async def update(
        self,
        ctx: ActionContext,
        instance: models.Model,
        data: dict[str, Any],
    ) -> models.Model: ...

    async def delete(self, ctx: ActionContext, instance: models.Model) -> None: ...


__all__ = ["StateBackend"]
