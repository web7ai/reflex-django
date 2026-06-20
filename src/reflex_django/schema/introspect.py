"""Build :class:`~reflex_django.schema.fieldspec.FieldSpec` lists from Django models."""

from __future__ import annotations

from collections.abc import Sequence

from django.db import models

from reflex_django.schema.fieldspec import (
    KIND_BOOL,
    KIND_DATE,
    KIND_DATETIME,
    KIND_DECIMAL,
    KIND_FLOAT,
    KIND_INT,
    KIND_RELATION,
    KIND_STR,
    KIND_TEXT,
    KIND_TIME,
    FieldSpec,
)

_INT_FIELDS: tuple[type[models.Field], ...] = (
    models.AutoField,
    models.BigAutoField,
    models.BigIntegerField,
    models.IntegerField,
    models.PositiveBigIntegerField,
    models.PositiveIntegerField,
    models.PositiveSmallIntegerField,
    models.SmallIntegerField,
)


def _kind_for(field: models.Field) -> str:
    if isinstance(field, models.ForeignKey):
        return KIND_RELATION
    if isinstance(field, models.BooleanField):
        return KIND_BOOL
    if isinstance(field, models.DecimalField):
        return KIND_DECIMAL
    if isinstance(field, models.FloatField):
        return KIND_FLOAT
    if isinstance(field, _INT_FIELDS):
        return KIND_INT
    if isinstance(field, models.DateTimeField):
        return KIND_DATETIME
    if isinstance(field, models.DateField):
        return KIND_DATE
    if isinstance(field, models.TimeField):
        return KIND_TIME
    if isinstance(field, models.TextField):
        return KIND_TEXT
    return KIND_STR


def _is_auto_timestamp(field: models.Field) -> bool:
    return bool(
        getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    )


def _spec_for(field: models.Field, *, force_read_only: bool) -> FieldSpec:
    name = field.attname if isinstance(field, models.ForeignKey) else field.name
    read_only = (
        force_read_only
        or field.primary_key
        or not getattr(field, "editable", True)
        or _is_auto_timestamp(field)
    )
    relation_to = None
    if isinstance(field, models.ForeignKey):
        related = field.related_model
        if related is not None:
            relation_to = f"{related._meta.app_label}.{related._meta.object_name}"
    label = str(getattr(field, "verbose_name", name) or name)
    return FieldSpec(
        name=name,
        kind=_kind_for(field),
        required=not getattr(field, "blank", False) and not read_only,
        read_only=read_only,
        max_length=getattr(field, "max_length", None),
        choices=tuple(getattr(field, "choices", None) or ()),
        relation_to=relation_to,
        help_text=str(getattr(field, "help_text", "") or ""),
        label=label.title() if label.islower() else label,
    )


def model_field_specs(
    model: type[models.Model],
    fields: Sequence[str] | None = None,
    *,
    read_only: Sequence[str] = (),
) -> list[FieldSpec]:
    """Return :class:`FieldSpec` objects for *model*.

    Args:
        model: The Django model to introspect.
        fields: Restrict to these field names (by ``name`` or FK ``attname``);
            defaults to all concrete fields.
        read_only: Extra field names to force read-only.

    The primary key, non-editable fields, and auto timestamps are always marked
    read-only. Many-to-many and reverse relations are skipped.
    """
    read_only_set = set(read_only)
    by_name: dict[str, FieldSpec] = {}
    for field in model._meta.concrete_fields:
        name = field.attname if isinstance(field, models.ForeignKey) else field.name
        spec = _spec_for(field, force_read_only=name in read_only_set)
        by_name[name] = spec
        if isinstance(field, models.ForeignKey):
            by_name[field.name] = spec

    if fields is None:
        ordered = []
        seen: set[str] = set()
        for field in model._meta.concrete_fields:
            name = field.attname if isinstance(field, models.ForeignKey) else field.name
            if name not in seen:
                ordered.append(by_name[name])
                seen.add(name)
        return ordered

    selected: list[FieldSpec] = []
    missing: list[str] = []
    for raw in fields:
        key = str(raw).strip()
        if not key:
            continue
        spec = by_name.get(key)
        if spec is None:
            missing.append(key)
            continue
        selected.append(spec)
    if missing:
        valid = ", ".join(sorted(by_name)) or "(none)"
        msg = (
            f"Unknown field(s) for {model.__name__}: {', '.join(missing)}. "
            f"Available: {valid}."
        )
        raise ValueError(msg)
    return selected


__all__ = ["model_field_specs"]
