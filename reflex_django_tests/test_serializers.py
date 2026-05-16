"""Tests for :mod:`reflex_django.serializers`."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest import mock

from django.db import models

from reflex_django.conf import configure_django
from reflex_django.serializers import ReflexDjangoModelSerializer

configure_django()


class _Note(models.Model):
    title = models.CharField(max_length=64)
    content = models.TextField(blank=True)
    secret = models.CharField(max_length=8, default="x")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "reflex_django_tests"


class _NoteFieldsSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = _Note
        fields = ("title", "content", "created_at")


class _NoteExcludeSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = _Note
        exclude = ("secret",)


def _note(pk: int = 1, title: str = "hi") -> _Note:
    return _Note(
        pk=pk,
        title=title,
        content="body",
        secret="hidden",
        created_at=datetime(2024, 3, 1, 12, 0),
    )


def test_single_instance_data() -> None:
    data = _NoteFieldsSerializer(_note()).data
    assert data["title"] == "hi"
    assert data["content"] == "body"
    assert data["id"] == 1
    assert "secret" not in data
    assert data["created_at"] == "2024-03-01 12:00"


def test_many_queryset_data() -> None:
    qs = [_note(1), _note(2, title="two")]
    data = _NoteFieldsSerializer(qs, many=True).data
    assert len(data) == 2
    assert data[1]["title"] == "two"


def test_auto_many_for_queryset() -> None:
    from django.db.models import QuerySet

    qs = mock.MagicMock(spec=QuerySet)
    qs.__iter__ = mock.Mock(return_value=iter([_note(1)]))
    data = _NoteFieldsSerializer(qs).data
    assert len(data) == 1
    assert data[0]["id"] == 1


def test_meta_exclude() -> None:
    data = _NoteExcludeSerializer(_note()).data
    assert "secret" not in data
    assert "title" in data


def test_runtime_exclude_fields() -> None:
    data = _NoteFieldsSerializer(
        _note(),
        exclude_fields=frozenset({"content"}),
    ).data
    assert "content" not in data
    assert "title" in data


def test_alist_async_queryset() -> None:
    notes = [_note(1), _note(2)]

    async def _async_qs() -> Any:
        for n in notes:
            yield n

    async def run() -> list[dict[str, Any]]:
        return await _NoteFieldsSerializer(_async_qs(), many=True).adata()

    data = asyncio.run(run())
    assert len(data) == 2


def test_class_alist_shortcut() -> None:
    notes = [_note(1)]

    async def run() -> list[dict[str, Any]]:
        return await _NoteFieldsSerializer.alist(notes)

    data = asyncio.run(run())
    assert len(data) == 1


def test_class_list_shortcut() -> None:
    data = _NoteFieldsSerializer.list([_note(1), _note(2)])
    assert len(data) == 2


def test_get_read_only_includes_auto_and_serializer_meta() -> None:
    readonly = _NoteFieldsSerializer.get_read_only_field_names(
        extra_read_only=frozenset({"user"}),
    )
    assert "id" in readonly
    assert "created_at" in readonly
    assert "user" in readonly


def test_writable_field_names_excludes_read_only() -> None:
    names = _NoteFieldsSerializer.writable_field_names(
        read_only_fields=frozenset({"id", "created_at", "user"}),
    )
    assert names == ("content", "title")
    assert "created_at" not in names


def test_writable_field_names_explicit_state_fields() -> None:
    names = _NoteFieldsSerializer.writable_field_names(
        state_fields=("title", "created_at"),
    )
    assert names == ("title", "created_at")
