"""Single-object retrieval hooks."""

from __future__ import annotations

from typing import Any

from django.db import models

from reflex_django.state.base import ActionContext, BaseModelState
from reflex_django.state.mixins.queryset import QuerySetMixin


class ObjectMixin(QuerySetMixin):
    """``get_object`` / ``get_object_lookup`` hooks."""

    def get_object_lookup(self, pk: int) -> dict[str, Any]:
        return {"pk": pk}

    async def get_object(self, ctx: ActionContext, pk: int) -> models.Model:
        opts = ctx.options
        lookup = self.get_object_lookup(pk)
        return await opts.model.objects.aget(**lookup)

    async def get_object_or_none(
        self,
        ctx: ActionContext,
        pk: int,
    ) -> models.Model | None:
        opts = ctx.options
        lookup = self.get_object_lookup(pk)
        try:
            return await opts.model.objects.aget(**lookup)
        except opts.model.DoesNotExist:
            return None


__all__ = ["ObjectMixin"]
