"""DRF-style declarative serializers for Django models (no rest_framework dependency)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

from asgiref.sync import sync_to_async
from django.db import models
from django.db.models import QuerySet

from reflex_django.serialization import serialize_model_row


class ReflexDjangoModelSerializer:
    """Serialize Django model instances to JSON-friendly dicts for Reflex state.

    Usage::

        class NoteSerializer(ReflexDjangoModelSerializer):
            class Meta:
                model = Note
                fields = ("id", "title", "content")

        self.notes = await NoteSerializer(qs, many=True).adata()
        row = NoteSerializer(note).data
    """

    class Meta:
        """Declarative options (override on subclasses)."""

        model: type[models.Model] | None = None
        fields: tuple[str, ...] | list[str] | None = None
        exclude: tuple[str, ...] | list[str] = ()
        datetime_format: str = "%Y-%m-%d %H:%M"
        date_format: str = "%Y-%m-%d"

    def __init__(
        self,
        instance: models.Model | QuerySet[Any] | Iterable[models.Model] | Any,
        *,
        many: bool | None = None,
        exclude_fields: frozenset[str] | None = None,
    ) -> None:
        if many is None:
            many = isinstance(instance, QuerySet)
        self.instance = instance
        self.many = many
        self._runtime_exclude = exclude_fields or frozenset()

    def _meta(self, name: str, default: Any) -> Any:
        meta = getattr(self.__class__, "Meta", None)
        if meta is None:
            return default
        return getattr(meta, name, default)

    def _resolved_exclude(self) -> frozenset[str]:
        meta_exclude = self._meta("exclude", ())
        return frozenset(meta_exclude) | self._runtime_exclude

    def _resolved_include_fields(self) -> frozenset[str] | None:
        raw = self._meta("fields", None)
        if raw is None:
            return None
        names = set(raw)
        names.add("id")
        return frozenset(names)

    def _serialize_one(self, obj: models.Model) -> dict[str, Any]:
        meta_model = self._meta("model", None)
        if meta_model is not None and not isinstance(obj, meta_model):
            msg = f"Expected {meta_model.__name__!r}, got {type(obj).__name__!r}."
            raise TypeError(msg)
        row = serialize_model_row(
            obj,
            exclude_fields=self._resolved_exclude(),
            datetime_format=self._meta("datetime_format", "%Y-%m-%d %H:%M"),
            date_format=self._meta("date_format", "%Y-%m-%d"),
        )
        include = self._resolved_include_fields()
        if include is not None:
            row = {key: row[key] for key in include if key in row}
        return row

    def _iter_sync(self) -> Iterator[models.Model]:
        if not self.many:
            yield self.instance  # type: ignore[misc]
            return
        yield from self.instance  # type: ignore[arg-type]

    async def _iter_async(self) -> AsyncIterator[models.Model]:
        if not self.many:
            yield self.instance  # type: ignore[misc]
            return
        if hasattr(self.instance, "__aiter__"):
            async for obj in self.instance:  # type: ignore[union-attr]
                yield obj
            return
        for obj in self.instance:  # type: ignore[arg-type]
            yield obj

    @property
    def data(self) -> dict[str, Any] | list[dict[str, Any]]:
        if self.many:
            return [self._serialize_one(obj) for obj in self._iter_sync()]
        return self._serialize_one(self.instance)  # type: ignore[arg-type]

    async def adata(self) -> dict[str, Any] | list[dict[str, Any]]:
        if not self.many:
            return await sync_to_async(self._serialize_one)(self.instance)
        rows: list[dict[str, Any]] = []
        async for obj in self._iter_async():
            rows.append(self._serialize_one(obj))
        return rows

    @classmethod
    def list(
        cls,
        queryset: QuerySet[Any] | Iterable[models.Model],
        *,
        exclude_fields: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Serialize a queryset or iterable synchronously."""
        return cls(queryset, many=True, exclude_fields=exclude_fields).data  # type: ignore[return-value]

    @classmethod
    async def alist(
        cls,
        queryset: QuerySet[Any] | Iterable[models.Model],
        *,
        exclude_fields: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Serialize a queryset or iterable asynchronously."""
        return await cls(queryset, many=True, exclude_fields=exclude_fields).adata()  # type: ignore[return-value]


__all__ = ["ReflexDjangoModelSerializer"]
