"""A single, framework-neutral description of a model field.

:class:`FieldSpec` is the one schema source the rest of reflex-django can derive
from: Reflex state var types, writable-field sets, and validation. Build specs
from a Django model (:mod:`reflex_django.schema.introspect`) or adapt an existing
DRF ``ModelSerializer`` / Django ``ModelForm``
(:mod:`reflex_django.schema.adapters`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

Validator = Callable[[Any], str | None]

# Field "kinds" — semantic categories independent of any one framework.
KIND_STR = "str"
KIND_TEXT = "text"
KIND_INT = "int"
KIND_FLOAT = "float"
KIND_DECIMAL = "decimal"
KIND_BOOL = "bool"
KIND_DATE = "date"
KIND_DATETIME = "datetime"
KIND_TIME = "time"
KIND_RELATION = "relation"

# Reflex vars are limited to JSON-friendly scalars. Decimal/date/datetime have
# no native Reflex var type, so they round-trip as strings (the serializer emits
# formatted strings already); the exact Python type is preserved on the spec for
# server-side coercion and validation.
_VAR_TYPE_BY_KIND: dict[str, type] = {
    KIND_BOOL: bool,
    KIND_INT: int,
    KIND_RELATION: int,
    KIND_FLOAT: float,
}


@dataclass(frozen=True)
class FieldSpec:
    """One field's type/constraints, shared across serializer, state, and UI."""

    name: str
    kind: str = KIND_STR
    required: bool = False
    read_only: bool = False
    max_length: int | None = None
    choices: tuple[tuple[Any, str], ...] = ()
    relation_to: str | None = None
    help_text: str = ""
    label: str = ""
    validators: tuple[Validator, ...] = field(default_factory=tuple)

    @property
    def var_type(self) -> type:
        """Reflex state var type (``str`` for anything without a native var)."""
        return _VAR_TYPE_BY_KIND.get(self.kind, str)

    @property
    def is_relation(self) -> bool:
        return self.kind == KIND_RELATION

    @property
    def is_multiline(self) -> bool:
        return self.kind == KIND_TEXT


def field_names(specs: Sequence[FieldSpec]) -> tuple[str, ...]:
    """Return spec names in order."""
    return tuple(s.name for s in specs)


def writable_specs(specs: Sequence[FieldSpec]) -> tuple[FieldSpec, ...]:
    """Return only the editable (non read-only) specs."""
    return tuple(s for s in specs if not s.read_only)


def required_field_names(specs: Sequence[FieldSpec]) -> frozenset[str]:
    """Names of required, writable specs."""
    return frozenset(s.name for s in specs if s.required and not s.read_only)


__all__ = [
    "KIND_BOOL",
    "KIND_DATE",
    "KIND_DATETIME",
    "KIND_DECIMAL",
    "KIND_FLOAT",
    "KIND_INT",
    "KIND_RELATION",
    "KIND_STR",
    "KIND_TEXT",
    "KIND_TIME",
    "FieldSpec",
    "Validator",
    "field_names",
    "required_field_names",
    "writable_specs",
]
