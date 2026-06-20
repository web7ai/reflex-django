"""Turn :class:`~reflex_django.schema.fieldspec.FieldSpec` lists into state fields."""

from __future__ import annotations

from collections.abc import Sequence

from reflex_django.schema.fieldspec import (
    KIND_BOOL,
    KIND_FLOAT,
    KIND_INT,
    KIND_RELATION,
    FieldSpec,
    writable_specs,
)
from reflex_django.state.fields import (
    BoolStateField,
    FloatStateField,
    IntStateField,
    StateField,
    StrStateField,
)


def state_field_from_spec(spec: FieldSpec) -> StateField:
    """Map one :class:`FieldSpec` to the matching :class:`StateField` descriptor."""
    if spec.kind == KIND_BOOL:
        return BoolStateField(name=spec.name, required=spec.required)
    if spec.kind == KIND_FLOAT:
        return FloatStateField(name=spec.name, required=spec.required)
    if spec.kind in (KIND_INT, KIND_RELATION):
        return IntStateField(name=spec.name, required=spec.required)
    return StrStateField(name=spec.name, required=spec.required)


def build_state_fields_from_specs(
    specs: Sequence[FieldSpec],
    *,
    writable_only: bool = True,
) -> tuple[StateField, ...]:
    """Build state field descriptors from specs (writable specs by default)."""
    chosen = writable_specs(specs) if writable_only else tuple(specs)
    return tuple(state_field_from_spec(s) for s in chosen)


__all__ = ["build_state_fields_from_specs", "state_field_from_spec"]
