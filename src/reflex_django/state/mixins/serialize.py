"""Serialization hooks."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.base import ActionContext, BaseModelState
from reflex_django.state.mixins.queryset import QuerySetMixin


class SerializeMixin(QuerySetMixin):
    """Serialize querysets via :class:`~reflex_django.serializers.ReflexDjangoModelSerializer`."""

    def get_serializer(
        self,
        instance: Any,
        *,
        many: bool = False,
    ) -> ReflexDjangoModelSerializer:
        opts = self.get_options()
        return opts.serializer_class(
            instance,
            many=many,
            exclude_fields=opts.exclude_from_row,
        )

    async def serialize_queryset(self, ctx: ActionContext) -> list[dict[str, Any]]:
        qs = self.get_scoped_queryset()
        serializer = self.get_serializer(qs, many=True)
        return await serializer.adata()  # type: ignore[return-value]


__all__ = ["SerializeMixin"]
