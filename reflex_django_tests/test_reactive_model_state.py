"""Tests for :class:`~reflex_django.state.generic.ModelState` reactive ORM API."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import reflex as rx
from django.core.exceptions import ImproperlyConfigured
from django.db import models

from reflex_django.conf import configure_django

configure_django()

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state import (
    AppState,
    ModelCRUDView,
    ModelState,
    build_serializer_from_fields,
    validate_model_fields,
)
from reflex_django.state.serializer_factory import _SERIALIZER_CACHE


class RmProduct(models.Model):
    name = models.CharField(max_length=64)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "reflex_django_tests"


class RmCategory(models.Model):
    label = models.CharField(max_length=32)

    class Meta:
        app_label = "reflex_django_tests"


class ProductState(ModelState[RmProduct]):
    model = RmProduct
    fields = ["name", "price", "is_active"]


class CategoryState(ModelState[RmCategory]):
    model = RmCategory
    fields = ["label"]


class _LegacyExplicitState(AppState, ModelCRUDView):
    class Meta:
        serializer = type(
            "RmProductSerializer",
            (ReflexDjangoModelSerializer,),
            {
                "Meta": type(
                    "Meta",
                    (),
                    {
                        "model": RmProduct,
                        "fields": ("id", "name", "price", "is_active"),
                    },
                )
            },
        )


class _CustomSaveModelState(ModelState[RmProduct]):
    model = RmProduct
    fields = ["name", "price"]

    @rx.event
    async def save(self) -> str:
        return "custom"


class _NoCanonicalState(ModelState[RmProduct]):
    model = RmProduct
    fields = ["name"]

    class Meta:
        use_canonical_api = False


def test_build_serializer_from_fields_includes_id() -> None:
    _SERIALIZER_CACHE.clear()
    ser_cls = build_serializer_from_fields(RmProduct, ["name", "price"])
    assert ser_cls.Meta.model is RmProduct
    assert "id" in ser_cls.Meta.fields
    assert "name" in ser_cls.Meta.fields


def test_validate_model_fields_rejects_unknown() -> None:
    try:
        validate_model_fields(RmProduct, ["name", "not_a_field"])
    except ImproperlyConfigured as exc:
        assert "not_a_field" in str(exc)
    else:
        raise AssertionError("expected ImproperlyConfigured")


def test_product_state_auto_serializer_and_vars() -> None:
    assert hasattr(ProductState, "products")
    assert hasattr(ProductState, "name")
    assert hasattr(ProductState, "price")
    assert hasattr(ProductState, "is_active")
    assert ProductState.__annotations__["products"] == list[dict[str, Any]]
    cfg = ProductState.get_options()
    assert cfg.model is RmProduct
    assert cfg.use_canonical_api is True


def test_canonical_handlers_generated() -> None:
    for name in (
        "load",
        "save",
        "create",
        "delete",
        "refresh",
        "filter",
        "clear_filter",
        "paginate",
    ):
        assert hasattr(ProductState, name), name
    assert hasattr(ProductState, f"save_{ProductState.get_options().model._meta.model_name}")
    assert hasattr(ProductState, "start_edit")


def test_second_model_state_independent_list_var() -> None:
    assert hasattr(CategoryState, "categories")
    assert "label" in CategoryState.__annotations__
    assert "name" not in CategoryState.__annotations__


def test_legacy_model_crud_view_still_works() -> None:
    assert hasattr(_LegacyExplicitState, "save_rmproduct")
    assert hasattr(_LegacyExplicitState, "load")
    assert issubclass(_LegacyExplicitState, ModelCRUDView)


def test_subclass_save_override_replaces_canonical() -> None:
    assert "save" in _CustomSaveModelState.__dict__

    async def run() -> None:
        assert await _CustomSaveModelState().save() == "custom"

    asyncio.run(run())


def test_use_canonical_api_false_skips_canonical_handlers() -> None:
    assert not hasattr(_NoCanonicalState, "load")
    opts = _NoCanonicalState.get_options()
    assert hasattr(_NoCanonicalState, f"save_{opts.model._meta.model_name}")


def test_filter_queryset_applies_stored_filter() -> None:
    qs = mock.MagicMock()
    filtered = mock.MagicMock()
    qs.filter.return_value = filtered
    state = ProductState()
    state._queryset_filter = {"is_active": True}
    with mock.patch.object(RmProduct, "objects") as mgr:
        mgr.all.return_value = qs
        result = state.filter_queryset(qs)
    qs.filter.assert_called_once_with(is_active=True)
    assert result is filtered


def test_get_row_reads_from_list_var() -> None:
    state = ProductState()
    state.products = [
        {"id": 1, "name": "A", "price": "1.00", "is_active": True},
        {"id": 2, "name": "B", "price": "2.00", "is_active": False},
    ]
    row = state.get_row(2)
    assert row is not None
    assert row["name"] == "B"


def test_missing_fields_raises_at_class_creation() -> None:
    try:

        class _BadState(ModelState[RmProduct]):
            model = RmProduct

    except ImproperlyConfigured as exc:
        assert "fields" in str(exc).lower()
    else:
        raise AssertionError("expected ImproperlyConfigured")
