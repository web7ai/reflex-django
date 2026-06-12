"""Tests for :class:`~reflex_django.state.generic.ModelState` reactive ORM API."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import reflex as rx
from django.core.exceptions import ImproperlyConfigured
from django.db import models

from reflex_django.setup.conf import configure_django

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


class ProductState(ModelState):
    model = RmProduct
    fields = ["name", "price", "is_active"]


class CategoryState(ModelState):
    model = RmCategory
    fields = ["label"]


class _ProductStateFromGeneric(ModelState[RmProduct]):
    """Optional: model inferred from ``ModelState[RmProduct]`` without class-body ``model``."""
    fields = ["name", "price"]


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


class _CustomSaveModelState(ModelState):
    model = RmProduct
    fields = ["name", "price"]

    @rx.event
    async def save(self) -> str:
        return "custom"


class _NoCanonicalState(ModelState):
    model = RmProduct
    fields = ["name"]

    class Meta:
        use_canonical_api = False


class _SearchProductState(ModelState):
    model = RmProduct
    fields = ["name", "price"]

    class Meta:
        search_fields = ("name",)
        paginate_by = 10


class _PaginatedProductState(ModelState):
    model = RmProduct
    fields = ["name", "price"]

    class Meta:
        paginate_by = 20


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


def test_model_from_class_body() -> None:
    assert ProductState.model is RmProduct
    assert CategoryState.model is RmCategory


def test_model_inferred_from_optional_generic_subscript() -> None:
    assert _ProductStateFromGeneric.model is RmProduct


def test_model_state_pagination_uses_paginate_by_page_size() -> None:
    assert _PaginatedProductState.get_options().paginate_by == 20
    assert _PaginatedProductState.__dict__["page_size"] == 20
    state = _PaginatedProductState()
    assert state.get_page_size() == 20
    qs = mock.MagicMock()
    state.paginate_queryset(qs)
    qs.__getitem__.assert_called_once_with(slice(0, 20))


def test_default_search_and_pagination_var_names() -> None:
    cfg = _SearchProductState.get_options()
    assert cfg.search_var == "search"
    assert cfg.total_count_var == "total_count"
    assert cfg.page_count_var == "page_count"
    assert hasattr(_SearchProductState, "set_search")
    assert hasattr(_SearchProductState, "clear_search")
    assert hasattr(_SearchProductState, "_load_data")
    assert hasattr(_SearchProductState, "on_load_data")


def test_product_state_auto_serializer_and_vars() -> None:
    assert hasattr(ProductState, "data")
    assert hasattr(ProductState, "name")
    assert hasattr(ProductState, "price")
    assert hasattr(ProductState, "is_active")
    assert ProductState.__annotations__["data"] == list[dict[str, Any]]
    cfg = ProductState.get_options()
    assert cfg.model is RmProduct
    assert cfg.list_var == "data"
    assert cfg.error_var == "error"
    assert cfg.search_var == "search"
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


def test_second_model_state_shares_default_var_names_per_class() -> None:
    assert hasattr(CategoryState, "data")
    assert hasattr(ProductState, "data")
    assert CategoryState.get_options().list_var == "data"
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


def test_save_update_clears_fields_and_bumps_form_reset_key() -> None:
    inst = mock.Mock(pk=2)
    inst.name = "old"
    inst.price = 0
    inst.is_active = True

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.decorators.current_user",
            ) as cu,
            mock.patch.object(RmProduct, "objects") as mgr,
            mock.patch.object(ProductState, "refresh", new=mock.AsyncMock()),
        ):
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            mgr.aget = mock.AsyncMock(return_value=inst)
            inst.asave = mock.AsyncMock()
            state = ProductState()
            state.editing_id = 2
            state.name = "updated"
            state.price = 5
            state.is_active = False
            await state.save()
            assert state.name == ""
            assert state.price == 0
            assert state.is_active is False
            assert state.editing_id == -1
            assert state.form_reset_key == 1

    asyncio.run(run())


def test_get_row_reads_from_list_var() -> None:
    state = ProductState()
    state.data = [
        {"id": 1, "name": "A", "price": "1.00", "is_active": True},
        {"id": 2, "name": "B", "price": "2.00", "is_active": False},
    ]
    row = state.get_row(2)
    assert row is not None
    assert row["name"] == "B"


def test_missing_fields_raises_at_class_creation() -> None:
    try:

        class _BadState(ModelState):
            model = RmProduct

    except ImproperlyConfigured as exc:
        assert "fields" in str(exc).lower()
    else:
        raise AssertionError("expected ImproperlyConfigured")
