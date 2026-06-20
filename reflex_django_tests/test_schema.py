"""Tests for the unified FieldSpec schema layer and its adapters."""

from __future__ import annotations

import pytest
from django.db import models

from reflex_django.setup.conf import configure_django

configure_django()

from django import forms  # noqa: E402

from reflex_django.schema import (  # noqa: E402
    FieldSpec,
    build_state_fields_from_specs,
    fieldspecs_from_drf_serializer,
    fieldspecs_from_model_form,
    model_field_specs,
)
from reflex_django.schema.fieldspec import (  # noqa: E402
    KIND_BOOL,
    KIND_DATETIME,
    KIND_DECIMAL,
    KIND_FLOAT,
    KIND_INT,
    KIND_RELATION,
    KIND_STR,
    KIND_TEXT,
)
from reflex_django.state.fields import (  # noqa: E402
    BoolStateField,
    FloatStateField,
    IntStateField,
    StrStateField,
)


class ScWidget(models.Model):
    title = models.CharField(max_length=50)
    body = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    rating = models.FloatField(default=0)
    count = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "reflex_django_tests"


def _by_name(specs) -> dict[str, FieldSpec]:
    return {s.name: s for s in specs}


def test_model_field_specs_kinds_and_read_only() -> None:
    specs = _by_name(model_field_specs(ScWidget))
    assert specs["id"].read_only is True
    assert specs["id"].kind == KIND_INT
    assert specs["title"].kind == KIND_STR
    assert specs["title"].required is True
    assert specs["body"].kind == KIND_TEXT
    assert specs["body"].required is False
    assert specs["price"].kind == KIND_DECIMAL
    assert specs["rating"].kind == KIND_FLOAT
    assert specs["count"].kind == KIND_INT
    assert specs["active"].kind == KIND_BOOL
    assert specs["owner_id"].kind == KIND_RELATION
    assert specs["owner_id"].relation_to == "auth.User"
    assert specs["created"].kind == KIND_DATETIME
    assert specs["created"].read_only is True


def test_fieldspec_var_types() -> None:
    specs = _by_name(model_field_specs(ScWidget))
    assert specs["title"].var_type is str
    assert specs["price"].var_type is str  # Decimal has no Reflex var type
    assert specs["created"].var_type is str
    assert specs["rating"].var_type is float
    assert specs["count"].var_type is int
    assert specs["active"].var_type is bool
    assert specs["owner_id"].var_type is int


def test_model_field_specs_explicit_fields_and_missing() -> None:
    specs = model_field_specs(ScWidget, ["title", "owner"])
    assert [s.name for s in specs] == ["title", "owner_id"]
    with pytest.raises(ValueError):
        model_field_specs(ScWidget, ["nope"])


def test_build_state_fields_from_specs_types() -> None:
    fields = {
        f.name: f for f in build_state_fields_from_specs(model_field_specs(ScWidget))
    }
    # read-only fields are excluded by default
    assert "id" not in fields
    assert "created" not in fields
    assert isinstance(fields["title"], StrStateField)
    assert isinstance(fields["price"], StrStateField)  # Decimal -> str var
    assert isinstance(fields["rating"], FloatStateField)
    assert isinstance(fields["count"], IntStateField)
    assert isinstance(fields["active"], BoolStateField)
    assert isinstance(fields["owner_id"], IntStateField)


def test_model_form_adapter() -> None:
    class ScWidgetForm(forms.ModelForm):
        class Meta:
            model = ScWidget
            fields = ["title", "body", "rating", "active"]

    specs = _by_name(fieldspecs_from_model_form(ScWidgetForm))
    assert specs["title"].kind == KIND_STR
    assert specs["body"].kind == KIND_TEXT  # TextField -> Textarea widget
    assert specs["rating"].kind == KIND_FLOAT
    assert specs["active"].kind == KIND_BOOL


class _IntegerField:
    pass


class _CharField:
    pass


class _BooleanField:
    pass


class _PrimaryKeyRelatedField:
    pass


def _drf_field(cls, *, read_only=False, required=True, max_length=None):
    obj = cls()
    obj.read_only = read_only
    obj.required = required
    obj.label = ""
    obj.help_text = ""
    obj.max_length = max_length
    return obj


class _FakeSerializer:
    def __init__(self) -> None:
        self.fields = {
            "id": _drf_field(_IntegerField, read_only=True, required=False),
            "name": _drf_field(_CharField, max_length=100),
            "is_active": _drf_field(_BooleanField, required=False),
            "owner": _drf_field(_PrimaryKeyRelatedField),
        }


def test_drf_serializer_adapter() -> None:
    specs = _by_name(fieldspecs_from_drf_serializer(_FakeSerializer))
    assert specs["id"].kind == KIND_INT
    assert specs["id"].read_only is True
    assert specs["name"].kind == KIND_STR
    assert specs["name"].max_length == 100
    assert specs["is_active"].kind == KIND_BOOL
    assert specs["owner"].kind == KIND_RELATION
