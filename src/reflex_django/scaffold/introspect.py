"""Map unified :class:`FieldSpec` data onto scaffold form widgets."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import models

from reflex_django.schema.fieldspec import (
    KIND_BOOL,
    KIND_DECIMAL,
    KIND_FLOAT,
    KIND_INT,
    KIND_RELATION,
    KIND_TEXT,
    FieldSpec,
)
from reflex_django.schema.introspect import model_field_specs


@dataclass(frozen=True)
class ScaffoldField:
    """A single editable model field rendered by the scaffold generator."""

    name: str
    widget: str
    label: str
    required: bool


_DATETIME_KINDS = {"date", "datetime", "time"}


def _widget_for(spec: FieldSpec) -> str:
    if spec.kind == KIND_BOOL:
        return "bool"
    if spec.kind == KIND_TEXT:
        return "textarea"
    if spec.kind in (KIND_RELATION, KIND_INT, KIND_FLOAT, KIND_DECIMAL):
        return "number"
    if spec.kind in _DATETIME_KINDS:
        return "datetime"
    return "text"


def _scaffold_field(spec: FieldSpec) -> ScaffoldField:
    label = spec.label or spec.name
    return ScaffoldField(
        name=spec.name,
        widget=_widget_for(spec),
        label=label.title() if label.islower() else label,
        required=spec.required,
    )


def editable_fields(model: type[models.Model]) -> list[ScaffoldField]:
    """Return editable scalar/FK fields for *model* in declaration order.

    Built from the unified :func:`~reflex_django.schema.model_field_specs`
    source, then filtered to writable specs (skips the primary key, auto
    timestamps, non-editable fields, and relations the scaffold cannot render
    as a single input).
    """
    return [
        _scaffold_field(spec) for spec in model_field_specs(model) if not spec.read_only
    ]


__all__ = ["ScaffoldField", "editable_fields"]
