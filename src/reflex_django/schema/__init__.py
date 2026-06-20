"""Unified field schema: one ``FieldSpec`` source for serializer, state, and UI.

Build specs from a Django model, or adapt an existing DRF ``ModelSerializer`` or
Django ``ModelForm`` as the single schema source::

    from reflex_django.schema import model_field_specs, build_state_fields_from_specs

    specs = model_field_specs(Product)
    state_fields = build_state_fields_from_specs(specs)

This removes the divergence between ``ModelState.fields``, serializer
``Meta.fields``, and hand-written ``StateField`` types.
"""

from __future__ import annotations

from reflex_django.schema.adapters import (
    fieldspecs_from_drf_serializer,
    fieldspecs_from_model_form,
)
from reflex_django.schema.fieldspec import (
    FieldSpec,
    field_names,
    required_field_names,
    writable_specs,
)
from reflex_django.schema.introspect import model_field_specs
from reflex_django.schema.state_bridge import (
    build_state_fields_from_specs,
    state_field_from_spec,
)

__all__ = [
    "FieldSpec",
    "build_state_fields_from_specs",
    "field_names",
    "fieldspecs_from_drf_serializer",
    "fieldspecs_from_model_form",
    "model_field_specs",
    "required_field_names",
    "state_field_from_spec",
    "writable_specs",
]
