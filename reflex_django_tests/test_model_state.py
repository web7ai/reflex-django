"""Tests for :mod:`reflex_django.state` (:class:`ModelState`)."""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest import mock

import reflex as rx
from django.db import models

from reflex_django.conf import configure_django
from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state import AppState, ModelState
from reflex_django.state._model_crud import resolve_model_state_config

configure_django()


class MsNote(models.Model):
    user_id = models.IntegerField()
    title = models.CharField(max_length=64)
    content = models.TextField(blank=True)
    description = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "reflex_django_tests"


class MsNoteSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = MsNote
        fields = ("id", "title", "content", "description", "created_at")
        read_only_fields = ("id", "created_at")


class _NotesState(AppState, ModelState):
    class Meta:
        serializer = MsNoteSerializer
        list_var = "notes"
        owner_field = "user_id"
        save_event = "save_note"
        delete_event = "delete_note"
        read_only_fields = ("user",)


class _CustomSaveState(AppState, ModelState):
    class Meta:
        serializer = MsNoteSerializer

    async def save_note(self) -> str:
        return "custom"


class _ExplicitFormState(AppState, ModelState):
    class Meta:
        serializer = MsNoteSerializer
        form_fields = ("title", "created_at")


def test_model_state_generates_annotations_and_handlers() -> None:
    ann = _NotesState.__annotations__
    assert ann["notes"] == list[dict[str, Any]]
    assert ann["notes_error"] is str
    assert ann["editing_id"] is int
    assert ann["title"] is str
    assert ann["content"] is str
    assert ann["description"] is str
    assert "created_at" not in ann
    assert hasattr(_NotesState, "set_title")
    assert hasattr(_NotesState, "_load_notes")
    assert hasattr(_NotesState, "on_load_notes")
    assert hasattr(_NotesState, "save_note")
    assert hasattr(_NotesState, "delete_note")
    assert hasattr(_NotesState, "start_edit")
    assert hasattr(_NotesState, "cancel_edit")
    assert getattr(sys.modules[__name__], "_NotesState") is _NotesState


def test_subclass_save_override_replaces_generated() -> None:
    assert "save_note" in _CustomSaveState.__dict__

    async def run() -> None:
        assert await _CustomSaveState().save_note() == "custom"

    asyncio.run(run())


def test_resolve_config_writable_fields() -> None:
    cfg = resolve_model_state_config(MsNoteSerializer, _NotesState.Meta)
    assert cfg.form_fields == ("content", "description", "title")
    assert "id" in cfg.read_only_fields
    assert "created_at" in cfg.read_only_fields
    assert "user" in cfg.read_only_fields


def test_explicit_form_fields_override_read_only() -> None:
    cfg = resolve_model_state_config(MsNoteSerializer, _ExplicitFormState.Meta)
    assert cfg.form_fields == ("title", "created_at")
    assert "created_at" in _ExplicitFormState.__annotations__


def test_serializer_writable_field_names() -> None:
    names = MsNoteSerializer.writable_field_names(owner_field="user")
    assert "title" in names
    assert "id" not in names
    assert "created_at" not in names
    assert "user" not in names


def test_load_notes_assigns_serialized_rows() -> None:
    rows = [{"id": 1, "title": "a", "content": "", "description": ""}]
    user = mock.Mock(pk=7)

    qs = mock.MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.state._model_crud.require_login_user",
                return_value=user,
            ),
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(
                MsNoteSerializer,
                "adata",
                new=mock.AsyncMock(return_value=rows),
            ) as adata,
        ):
            mgr.all.return_value = qs
            state = _NotesState()
            with mock.patch(
                "reflex_django.auth.decorators.current_user",
            ) as cu:
                u = mock.Mock()
                u.is_authenticated = True
                cu.return_value = u
                await state._load_notes()
            mgr.all.assert_called_once()
            qs.filter.assert_called_once_with(user_id=user)
            qs.order_by.assert_called_once_with("-created_at")
            adata.assert_awaited_once()
            assert state.notes == rows

    asyncio.run(run())


def test_save_note_create_calls_orm() -> None:
    user = mock.Mock(pk=3)

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.state._model_crud.require_login_user",
                return_value=user,
            ),
            mock.patch(
                "reflex_django.auth.decorators.current_user",
            ) as cu,
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(_NotesState, "_load_notes", new=mock.AsyncMock()),
        ):
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            mgr.acreate = mock.AsyncMock()
            state = _NotesState()
            state.title = "t"
            state.content = "c"
            state.description = "d"
            await state.save_note()
            mgr.acreate.assert_awaited_once_with(
                title="t",
                content="c",
                description="d",
                user_id=user,
            )

    asyncio.run(run())


def test_app_state_model_state_mro() -> None:
    assert issubclass(_NotesState, AppState)
    assert issubclass(_NotesState, ModelState)  # mixin, not a second rx.State parent
    assert issubclass(_NotesState, rx.State)
