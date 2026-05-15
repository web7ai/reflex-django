"""Tests for :mod:`reflex_django.mixins.crud` (no database)."""

from __future__ import annotations

import sys
from typing import Any

import reflex as rx

from reflex_django.mixins.crud import (
    ModelCRUDConfig,
    _default_row_serializer,
    crud_mixin,
)


class _FakeRowModel:
    """Stand-in for a Django model at **class build** time (ORM not invoked)."""

    DoesNotExist = type("DoesNotExist", (Exception,), {})


class _AppStub(rx.State):
    app_flag: bool = False


def test_crud_mixin_builds_rx_state_subclass_and_registers_module() -> None:
    cfg = ModelCRUDConfig(
        model=_FakeRowModel,  # type: ignore[arg-type]
        list_var="widgets",
        form_fields=("title", "body"),
        error_var="widgets_error",
        refresh_method="_reload_widgets",
        on_load_event="on_load_widgets",
        add_event="add_widget",
        delete_event="delete_widget",
    )
    Cls = crud_mixin(cfg, state_module=__name__)
    assert issubclass(Cls, rx.State)
    assert Cls.__name__ == "_FakeRowModelCRUDState"
    assert Cls.__module__ == __name__
    ann = Cls.__annotations__
    assert ann["widgets"] == list[dict[str, Any]]
    assert ann["widgets_error"] is str
    assert ann["editing_id"] is int
    assert "form_title" in ann and "edit_title" in ann
    assert hasattr(Cls, "_reload_widgets")
    assert hasattr(Cls, "on_load_widgets")
    assert hasattr(Cls, "add_widget")
    assert hasattr(Cls, "delete_widget")
    assert hasattr(Cls, "start_edit")
    assert hasattr(Cls, "save_edit")
    assert hasattr(Cls, "cancel_edit")
    assert getattr(sys.modules[__name__], Cls.__name__) is Cls


def test_crud_mixin_accepts_custom_base() -> None:
    cfg = ModelCRUDConfig(
        model=_FakeRowModel,  # type: ignore[arg-type]
        list_var="rows",
        form_fields=("name",),
        error_var="rows_error",
    )
    Cls = crud_mixin(cfg, base=_AppStub, state_module=__name__)
    assert issubclass(Cls, _AppStub)
    assert issubclass(Cls, rx.State)


def test_default_row_serializer_includes_auto_now_add_fields() -> None:
    from datetime import datetime

    from django.db import models

    class _Stamped(models.Model):
        title = models.CharField(max_length=32)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = "reflex_django_tests"

    row = _Stamped(
        pk=1,
        title="x",
        created_at=datetime(2024, 1, 2, 3, 4),
    )
    data = _default_row_serializer(row, exclude_fields=frozenset())
    assert data["created_at"] == "2024-01-02 03:04"


def test_model_crud_config_row_datetime_format() -> None:
    from datetime import datetime

    from django.db import models

    class _Row(models.Model):
        title = models.CharField(max_length=32)
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = "reflex_django_tests"

    cfg = ModelCRUDConfig(
        model=_Row,  # type: ignore[arg-type]
        list_var="items",
        form_fields=("title",),
        error_var="items_error",
        row_datetime_format="%Y/%m/%d",
    )
    row = _Row(pk=1, title="t", created_at=datetime(2024, 5, 6, 7, 8))
    data = _default_row_serializer(
        row,
        exclude_fields=frozenset(),
        datetime_format=cfg.row_datetime_format,
        date_format=cfg.row_date_format,
    )
    assert data["created_at"] == "2024/05/06"


def test_mixins_package_reexports() -> None:
    from reflex_django.mixins import ModelCRUDConfig as MC
    from reflex_django.mixins import crud_mixin as cm

    assert MC is ModelCRUDConfig
    assert cm is crud_mixin
