"""Tests for :mod:`reflex_django.serializers.core`."""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

from django.db import models

from reflex_django.serializers.core import serialize_model_row


class _Stamped(models.Model):
    title = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_on = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "reflex_django_tests"


def test_serialize_model_row_includes_auto_timestamps() -> None:
    row = _Stamped(
        pk=1,
        title="x",
        created_at=datetime(2024, 1, 2, 3, 4),
        updated_at=datetime(2024, 6, 7, 8, 9),
    )
    data = serialize_model_row(row, exclude_fields=frozenset())
    assert data["created_at"] == "2024-01-02 03:04"
    assert data["updated_at"] == "2024-06-07 08:09"
    assert data["id"] == 1
    assert data["title"] == "x"


def test_serialize_model_row_formats_date_field() -> None:
    row = _Stamped(
        pk=2,
        title="y",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
        published_on=date(2024, 3, 15),
    )
    data = serialize_model_row(
        row,
        exclude_fields=frozenset(),
        date_format="%d/%m/%Y",
    )
    assert data["published_on"] == "15/03/2024"


def test_serialize_model_row_custom_datetime_format() -> None:
    row = _Stamped(
        pk=3,
        title="z",
        created_at=datetime(2024, 1, 2, 15, 30),
        updated_at=datetime(2024, 1, 2, 15, 30),
    )
    data = serialize_model_row(
        row,
        exclude_fields=frozenset(),
        datetime_format="%Y/%m/%d",
    )
    assert data["created_at"] == "2024/01/02"


def test_serialize_model_row_timezone_aware() -> None:
    aware = datetime(2024, 1, 2, 12, 0, tzinfo=dt_timezone.utc)
    row = _Stamped(
        pk=4,
        title="tz",
        created_at=aware,
        updated_at=aware,
    )
    data = serialize_model_row(row, exclude_fields=frozenset())
    assert isinstance(data["created_at"], str)
    assert len(data["created_at"]) > 0


def test_serialize_model_row_respects_exclude_fields() -> None:
    row = _Stamped(
        pk=5,
        title="hidden",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )
    data = serialize_model_row(row, exclude_fields=frozenset({"title"}))
    assert "title" not in data
    assert "created_at" in data
