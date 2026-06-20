"""Adapt existing DRF ``ModelSerializer`` / Django ``ModelForm`` into FieldSpecs.

These adapters are dependency-free: ``rest_framework`` is never imported. Field
kinds are resolved by walking each field's class MRO names, so any DRF/forms
field subclass maps to the closest :class:`~reflex_django.schema.fieldspec.FieldSpec`
kind.
"""

from __future__ import annotations

from typing import Any

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

# Class-name fragments → kind, checked against each field's MRO (most specific
# first). Order matters: relation and decimal before the generic fallbacks.
_KIND_BY_CLASSNAME: tuple[tuple[str, str], ...] = (
    ("RelatedField", KIND_RELATION),
    ("ModelChoiceField", KIND_RELATION),
    ("BooleanField", KIND_BOOL),
    ("DecimalField", KIND_DECIMAL),
    ("FloatField", KIND_FLOAT),
    ("IntegerField", KIND_INT),
    ("DateTimeField", KIND_DATETIME),
    ("DateField", KIND_DATE),
    ("TimeField", KIND_TIME),
)


def _kind_from_field_class(field_obj: Any) -> str:
    names = [cls.__name__ for cls in type(field_obj).__mro__]
    for fragment, kind in _KIND_BY_CLASSNAME:
        if any(fragment in name for name in names):
            return kind
    # Multiline char fields (Textarea widget) → text.
    widget = getattr(field_obj, "widget", None)
    if widget is not None and "Textarea" in type(widget).__name__:
        return KIND_TEXT
    return KIND_STR


def fieldspecs_from_drf_serializer(serializer_cls: type[Any]) -> list[FieldSpec]:
    """Build FieldSpecs from a DRF ``Serializer``/``ModelSerializer`` class.

    Reads the instantiated serializer's ``fields`` mapping (so declared and
    auto-generated model fields are both covered).
    """
    serializer = serializer_cls()
    fields = getattr(serializer, "fields", None)
    if not fields:
        msg = f"{serializer_cls.__name__} exposes no serializer fields."
        raise ValueError(msg)

    specs: list[FieldSpec] = []
    for name, field_obj in fields.items():
        read_only = bool(getattr(field_obj, "read_only", False))
        required = bool(getattr(field_obj, "required", False)) and not read_only
        label = str(getattr(field_obj, "label", "") or "")
        specs.append(
            FieldSpec(
                name=str(name),
                kind=_kind_from_field_class(field_obj),
                required=required,
                read_only=read_only,
                max_length=getattr(field_obj, "max_length", None),
                help_text=str(getattr(field_obj, "help_text", "") or ""),
                label=label,
            )
        )
    return specs


def fieldspecs_from_model_form(form_cls: type[Any]) -> list[FieldSpec]:
    """Build FieldSpecs from a Django ``Form``/``ModelForm`` class.

    Uses ``base_fields`` so no form instance/bound data is required.
    """
    base_fields = getattr(form_cls, "base_fields", None)
    if not base_fields:
        msg = f"{form_cls.__name__} declares no form fields."
        raise ValueError(msg)

    specs: list[FieldSpec] = []
    for name, field_obj in base_fields.items():
        required = bool(getattr(field_obj, "required", False))
        label = str(getattr(field_obj, "label", "") or "")
        specs.append(
            FieldSpec(
                name=str(name),
                kind=_kind_from_field_class(field_obj),
                required=required,
                read_only=getattr(field_obj, "disabled", False),
                max_length=getattr(field_obj, "max_length", None),
                help_text=str(getattr(field_obj, "help_text", "") or ""),
                label=label,
            )
        )
    return specs


__all__ = [
    "fieldspecs_from_drf_serializer",
    "fieldspecs_from_model_form",
]
