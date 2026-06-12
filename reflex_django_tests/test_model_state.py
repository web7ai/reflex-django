"""Tests for :mod:`reflex_django.state` (:class:`ModelCRUDView`)."""

from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest import mock

import reflex as rx
from django.db import models

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state import AppState, ModelCRUDView, ModelState, resolve_options
from reflex_django.state.fields import BoolStateField, StrStateField
from reflex_django.state.mixins.scoping import UserScopedMixin


class MsNote(models.Model):
    user_id = models.IntegerField()
    title = models.CharField(max_length=64)
    content = models.TextField(blank=True)
    description = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "reflex_django_tests"


class MsTask(models.Model):
    title = models.CharField(max_length=64)
    done = models.BooleanField(default=False)

    class Meta:
        app_label = "reflex_django_tests"
        ordering = ["-id"]


class MsNoteSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = MsNote
        fields = ("id", "title", "content", "description", "created_at")
        read_only_fields = ("id", "created_at")


class MsTaskSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = MsTask
        fields = ("id", "title", "done")
        read_only_fields = ("id",)


class _NotesState(AppState, ModelCRUDView, UserScopedMixin):
    scope_field = "user_id"

    class Meta:
        serializer = MsNoteSerializer
        list_var = "notes"
        save_event = "save_note"
        delete_event = "delete_note"
        read_only_fields = ("user",)


class _CustomSaveState(AppState, ModelCRUDView):
    serializer_class = MsNoteSerializer

    async def save_note(self) -> str:
        return "custom"


class _ExplicitStateFieldsState(AppState, ModelCRUDView):
    class Meta:
        serializer = MsNoteSerializer
        state_fields = ("title", "created_at")


class _PaginatedNotesState(AppState, ModelCRUDView, UserScopedMixin):
    scope_field = "user_id"

    class Meta:
        serializer = MsNoteSerializer
        list_var = "notes"
        paginate_by = 20


class _SearchNotesState(AppState, ModelCRUDView, UserScopedMixin):
    scope_field = "user_id"

    class Meta:
        serializer = MsNoteSerializer
        list_var = "notes"
        search_fields = ("title", "content")


def test_model_state_generates_annotations_and_handlers() -> None:
    ann = _NotesState.__annotations__
    assert ann["notes"] == list[dict[str, Any]]
    assert ann["notes_error"] is str
    assert ann["editing_id"] is int
    assert ann["form_reset_key"] is int
    assert ann["title"] is str
    assert ann["content"] is str
    assert ann["description"] is str
    assert "created_at" not in ann
    assert "page" not in ann
    assert "page_size" not in ann
    assert "notes_total_count" not in ann
    assert "notes_search" not in ann
    assert not hasattr(_NotesState, "next_page")
    assert hasattr(_NotesState, "set_title")
    assert hasattr(_NotesState, "_load_notes")
    assert hasattr(_NotesState, "on_load_notes")
    assert hasattr(_NotesState, "save_note")
    assert hasattr(_NotesState, "delete_note")
    assert hasattr(_NotesState, "start_edit")
    assert hasattr(_NotesState, "cancel_edit")
    assert hasattr(_NotesState, "load")
    assert hasattr(_NotesState, "save")
    assert hasattr(_NotesState, "refresh")
    assert hasattr(_NotesState, "reset_state_fields")
    assert hasattr(_NotesState, "_reset_state_fields")
    assert getattr(sys.modules[__name__], "_NotesState") is _NotesState


def test_model_state_is_generic_crud_base() -> None:
    assert ModelState is not ModelCRUDView
    assert issubclass(ModelState, AppState)
    assert issubclass(ModelState, ModelCRUDView)


def test_subclass_save_override_replaces_generated() -> None:
    assert "save_note" in _CustomSaveState.__dict__

    async def run() -> None:
        assert await _CustomSaveState().save_note() == "custom"

    asyncio.run(run())


def test_resolve_options_writable_fields() -> None:
    cfg = resolve_options(MsNoteSerializer, _NotesState.Meta, _NotesState)
    names = tuple(sf.name for sf in cfg.state_fields)
    assert names == ("content", "description", "title")
    assert "id" in cfg.read_only_fields
    assert "created_at" in cfg.read_only_fields
    assert cfg.ordering == ("-created_at",)


def test_resolve_options_ordering_from_model_meta() -> None:
    class _TaskState(AppState, ModelCRUDView):
        class Meta:
            serializer = MsTaskSerializer

    cfg = resolve_options(MsTaskSerializer, _TaskState.Meta, _TaskState)
    assert cfg.ordering == ("-id",)


def test_resolve_options_boolean_field_uses_bool_state_field() -> None:
    class _TaskState(AppState, ModelCRUDView):
        class Meta:
            serializer = MsTaskSerializer

    cfg = resolve_options(MsTaskSerializer, _TaskState.Meta, _TaskState)
    done_sf = next(sf for sf in cfg.state_fields if sf.name == "done")
    assert isinstance(done_sf, BoolStateField)
    assert _TaskState.__annotations__["done"] is bool


def test_explicit_state_fields_override_read_only() -> None:
    cfg = resolve_options(MsNoteSerializer, _ExplicitStateFieldsState.Meta, _ExplicitStateFieldsState)
    names = tuple(sf.name for sf in cfg.state_fields)
    assert names == ("title", "created_at")
    assert "created_at" in _ExplicitStateFieldsState.__annotations__


def test_serializer_writable_field_names() -> None:
    names = MsNoteSerializer.writable_field_names()
    assert "title" in names
    assert "id" not in names
    assert "created_at" not in names


def test_str_state_field_coercion() -> None:
    f = StrStateField(name="title")
    assert f.to_python("  x  ") == "x"
    assert f.to_var(None) == ""


def test_load_notes_assigns_serialized_rows() -> None:
    rows = [{"id": 1, "title": "a", "content": "", "description": ""}]
    user = mock.Mock(pk=7)

    qs = mock.MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.acount = mock.AsyncMock(return_value=len(rows))
    qs.__getitem__ = mock.Mock(return_value=qs)

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
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
            qs.filter.assert_called_once_with(user_id=7)
            qs.order_by.assert_called_once_with("-created_at")
            adata.assert_awaited_once()
            assert state.notes == rows

    asyncio.run(run())


def test_save_note_create_calls_orm() -> None:
    user = mock.Mock(pk=3)

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
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
                user_id=3,
            )
            assert state.title == ""
            assert state.content == ""
            assert state.description == ""
            assert state.editing_id == -1
            assert state.form_reset_key == 1

    asyncio.run(run())


def test_save_note_update_clears_form() -> None:
    user = mock.Mock(pk=3)
    inst = mock.Mock(pk=9)
    inst.title = "old"
    inst.content = "old body"
    inst.description = "old desc"

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
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
            mgr.aget = mock.AsyncMock(return_value=inst)
            inst.asave = mock.AsyncMock()
            state = _NotesState()
            state.editing_id = 9
            state.title = "new title"
            state.content = "new body"
            state.description = "new desc"
            await state.save_note()
            mgr.aget.assert_awaited_once_with(pk=9, user_id=3)
            inst.asave.assert_awaited_once()
            assert inst.title == "new title"
            assert state.title == ""
            assert state.content == ""
            assert state.description == ""
            assert state.editing_id == -1
            assert state.form_reset_key == 1

    asyncio.run(run())


def test_start_edit_bumps_form_reset_key() -> None:
    user = mock.Mock(pk=1)
    inst = mock.Mock(pk=4)
    inst.title = "loaded"
    inst.content = "body"
    inst.description = ""

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
                return_value=user,
            ),
            mock.patch(
                "reflex_django.auth.decorators.current_user",
            ) as cu,
            mock.patch.object(MsNote, "objects") as mgr,
        ):
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            mgr.aget = mock.AsyncMock(return_value=inst)
            state = _NotesState()
            assert state.form_reset_key == 0
            await state.start_edit(4)
            assert state.editing_id == 4
            assert state.title == "loaded"
            assert state.form_reset_key == 1

    asyncio.run(run())


def test_save_note_keeps_fields_when_reset_after_save_disabled() -> None:
    class _NoResetState(AppState, ModelCRUDView, UserScopedMixin):
        scope_field = "user_id"

        class Meta:
            serializer = MsNoteSerializer
            list_var = "notes"
            save_event = "save_note"
            reset_after_save = False

    user = mock.Mock(pk=2)

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
                return_value=user,
            ),
            mock.patch("reflex_django.auth.decorators.current_user") as cu,
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(_NoResetState, "_load_notes", new=mock.AsyncMock()),
        ):
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            mgr.acreate = mock.AsyncMock()
            state = _NoResetState()
            state.title = "keep"
            await state.save_note()
            assert state.title == "keep"
            assert state.form_reset_key == 0

    asyncio.run(run())


def test_save_note_form_applies_form_data() -> None:
    class _FormSubmitState(AppState, ModelCRUDView, UserScopedMixin):
        scope_field = "user_id"

        class Meta:
            serializer = MsNoteSerializer
            list_var = "notes"
            save_event = "save_note"
            use_form_submit = True

    user = mock.Mock(pk=4)

    async def run() -> None:
        with (
            mock.patch(
                "reflex_django.auth.shortcuts.require_login_user",
                return_value=user,
            ),
            mock.patch("reflex_django.auth.decorators.current_user") as cu,
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(_FormSubmitState, "_load_notes", new=mock.AsyncMock()),
        ):
            u = mock.Mock()
            u.is_authenticated = True
            cu.return_value = u
            mgr.acreate = mock.AsyncMock()
            state = _FormSubmitState()
            assert hasattr(_FormSubmitState, "save_note_form")
            await state.save_note_form(
                {
                    "title": "from-form",
                    "content": "body",
                    "description": "desc",
                }
            )
            mgr.acreate.assert_awaited_once_with(
                title="from-form",
                content="body",
                description="desc",
                user_id=4,
            )
            assert state.title == ""

    asyncio.run(run())


def test_app_state_model_state_mro() -> None:
    assert issubclass(_NotesState, AppState)
    assert issubclass(_NotesState, ModelCRUDView)
    assert issubclass(_NotesState, rx.State)


def _mock_note_qs(*, total: int = 1) -> mock.MagicMock:
    qs = mock.MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.acount = mock.AsyncMock(return_value=total)
    qs.__getitem__ = mock.Mock(return_value=qs)
    return qs


def test_paginated_state_generates_page_vars_and_events() -> None:
    cfg = resolve_options(MsNoteSerializer, _PaginatedNotesState.Meta, _PaginatedNotesState)
    assert cfg.paginate_by == 20
    assert cfg.total_count_var == "notes_total_count"
    assert hasattr(_PaginatedNotesState, "next_page")
    assert hasattr(_PaginatedNotesState, "prev_page")
    assert hasattr(_PaginatedNotesState, "go_to_page")
    assert hasattr(_PaginatedNotesState, "set_page_size")
    assert hasattr(_PaginatedNotesState, "set_notes_search") is False


def test_paginated_load_sets_metadata_and_slice() -> None:
    rows = [{"id": i, "title": f"t{i}", "content": "", "description": ""} for i in range(3)]
    user = mock.Mock(pk=1)
    qs = _mock_note_qs(total=45)

    async def run() -> None:
        with (
            mock.patch("reflex_django.auth.shortcuts.require_login_user", return_value=user),
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(
                MsNoteSerializer,
                "adata",
                new=mock.AsyncMock(return_value=rows),
            ),
        ):
            mgr.all.return_value = qs
            state = _PaginatedNotesState()
            with mock.patch("reflex_django.auth.decorators.current_user") as cu:
                u = mock.Mock()
                u.is_authenticated = True
                cu.return_value = u
                await state._load_notes()
            qs.__getitem__.assert_called_once_with(slice(0, 20))
            assert state.notes == rows
            assert state.notes_total_count == 45
            assert state.notes_page_count == 3
            assert state.page == 1

    asyncio.run(run())


def test_next_page_increments_and_reloads() -> None:
    user = mock.Mock(pk=1)
    qs = _mock_note_qs(total=50)

    async def run() -> None:
        with (
            mock.patch("reflex_django.auth.shortcuts.require_login_user", return_value=user),
            mock.patch.object(MsNote, "objects") as mgr,
            mock.patch.object(MsNoteSerializer, "adata", new=mock.AsyncMock(return_value=[])),
            mock.patch.object(_PaginatedNotesState, "_load_notes", new=mock.AsyncMock()) as load,
        ):
            mgr.all.return_value = qs
            state = _PaginatedNotesState()
            state.page = 1
            state.notes_page_count = 3
            with mock.patch("reflex_django.auth.decorators.current_user") as cu:
                u = mock.Mock()
                u.is_authenticated = True
                cu.return_value = u
                await state.next_page()
            assert state.page == 2
            load.assert_awaited_once()

    asyncio.run(run())


def test_search_state_generates_search_handlers() -> None:
    cfg = resolve_options(MsNoteSerializer, _SearchNotesState.Meta, _SearchNotesState)
    assert cfg.search_fields == ("title", "content")
    assert hasattr(_SearchNotesState, "set_notes_search")
    assert hasattr(_SearchNotesState, "clear_notes_search")


def test_apply_search_filters_queryset() -> None:
    user = mock.Mock(pk=1)
    qs = _mock_note_qs()
    state = _SearchNotesState()
    state.notes_search = "hello"
    filtered = mock.MagicMock()
    qs.filter.return_value = filtered

    with mock.patch.object(MsNote, "objects") as mgr:
        mgr.all.return_value = qs
        with mock.patch(
            "reflex_django.auth.shortcuts.require_login_user",
            return_value=user,
        ):
            result = state.apply_search(qs)

    qs.filter.assert_called_once()
    assert result is filtered


def test_bind_request_context_exposes_user() -> None:
    user = mock.Mock(pk=9)
    user.is_authenticated = True
    http = mock.Mock()
    http.user = user
    http.LANGUAGE_CODE = "en"

    async def run() -> None:
        with mock.patch(
            "reflex_django.bridge.context.current_request",
            return_value=http,
        ):
            state = _NotesState()
            await state.bind_request_context()
            assert object.__getattribute__(state, "_rd_django_request") is http
            assert state.request.user is user
            assert state.request.LANGUAGE_CODE == "en"
            state.teardown("load_list")
            assert object.__getattribute__(state, "_rd_request") is None
            assert object.__getattribute__(state, "_rd_django_request") is None

    asyncio.run(run())
