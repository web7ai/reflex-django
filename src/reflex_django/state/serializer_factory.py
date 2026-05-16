"""Build :class:`~reflex_django.serializers.ReflexDjangoModelSerializer` from model + fields."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import models

from reflex_django.serializers import ReflexDjangoModelSerializer

_SERIALIZER_CACHE: dict[tuple[type[models.Model], tuple[str, ...]], type] = {}


def _valid_field_names(model: type[models.Model]) -> set[str]:
    names: set[str] = set()
    for f in model._meta.get_fields():
        if getattr(f, "many_to_many", False) and getattr(f, "auto_created", False):
            continue
        if hasattr(f, "attname"):
            names.add(f.attname)
        elif hasattr(f, "name"):
            names.add(f.name)
    return names


def validate_model_fields(
    model: type[models.Model],
    fields: Sequence[str],
) -> tuple[str, ...]:
    """Return normalized field names or raise if any name is invalid on ``model``."""
    valid = _valid_field_names(model)
    normalized: list[str] = []
    invalid: list[str] = []
    for raw in fields:
        name = str(raw).strip()
        if not name:
            continue
        if name in valid:
            normalized.append(name)
        else:
            invalid.append(name)
    if invalid:
        model_label = f"{model._meta.app_label}.{model._meta.model_name}"
        msg = (
            f"Invalid fields for {model_label}: {', '.join(sorted(invalid))}. "
            f"Valid names include: {', '.join(sorted(valid)[:20])}"
            f"{'...' if len(valid) > 20 else ''}"
        )
        raise ImproperlyConfigured(msg)
    if not normalized:
        msg = f"At least one field is required for {model.__name__} ModelState."
        raise ImproperlyConfigured(msg)
    return tuple(dict.fromkeys(normalized))


def build_serializer_from_fields(
    model: type[models.Model],
    fields: Sequence[str],
    *,
    read_only_fields: Sequence[str] = (),
) -> type[ReflexDjangoModelSerializer]:
    """Create (or return cached) serializer class for ``model`` and ``fields``."""
    field_tuple = validate_model_fields(model, fields)
    read_only = tuple(read_only_fields or ())
    cache_key = (model, field_tuple, read_only)
    if cache_key in _SERIALIZER_CACHE:
        return _SERIALIZER_CACHE[cache_key]

    include = list(field_tuple)
    if "id" not in include:
        include.insert(0, "id")

    class _AutoSerializer(ReflexDjangoModelSerializer):
        class Meta:
            model = model
            fields = tuple(include)
            read_only_fields = read_only

    _AutoSerializer.__name__ = f"{model.__name__}Serializer"
    _AutoSerializer.__qualname__ = _AutoSerializer.__name__
    _SERIALIZER_CACHE[cache_key] = _AutoSerializer
    return _AutoSerializer


__all__ = ["build_serializer_from_fields", "validate_model_fields"]
