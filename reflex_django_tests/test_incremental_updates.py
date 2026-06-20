"""Tests for opt-in incremental list patching on ModelState."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from django.db import models

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state import AppState, ModelCRUDView
from reflex_django.state.mixins.list import ListMixin


class IuNote(models.Model):
    title = models.CharField(max_length=64)
    done = models.BooleanField(default=False)

    class Meta:
        app_label = "reflex_django_tests"


class IuNoteSerializer(ReflexDjangoModelSerializer):
    class Meta:
        model = IuNote
        fields = ("id", "title", "done")
        read_only_fields = ("id",)


@dataclass
class _Opts:
    list_var: str = "data"
    total_count_var: str = "total_count"
    paginate_by: int | None = None
    ordering: tuple[str, ...] = ("-id",)


@dataclass
class _Ctx:
    options: _Opts


class _FakeState(ListMixin):
    """Minimal ListMixin host with a stubbed single-row serializer."""

    def __init__(self, rows: list[dict[str, Any]], total: int = 0) -> None:
        self.data = list(rows)
        self.total_count = total
        self._next_row: dict[str, Any] = {}

    async def serialize_instance(self, ctx: Any, instance: Any) -> dict[str, Any]:
        return self._next_row


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_apply_saved_row_patches_existing_in_place() -> None:
    state = _FakeState([{"id": 1, "title": "a"}, {"id": 2, "title": "b"}], total=2)
    state._next_row = {"id": 2, "title": "B!"}
    ctx = _Ctx(_Opts())
    patched = _run(state.apply_saved_row(ctx, object(), was_create=False))
    assert patched is True
    assert state.data == [{"id": 1, "title": "a"}, {"id": 2, "title": "B!"}]
    assert state.total_count == 2  # unchanged on update


def test_apply_saved_row_insert_without_pagination_desc_order() -> None:
    state = _FakeState([{"id": 1, "title": "a"}], total=1)
    state._next_row = {"id": 5, "title": "new"}
    ctx = _Ctx(_Opts(paginate_by=None, ordering=("-id",)))
    patched = _run(state.apply_saved_row(ctx, object(), was_create=True))
    assert patched is True
    assert state.data[0] == {"id": 5, "title": "new"}
    assert state.total_count == 2


def test_apply_saved_row_insert_ascending_appends() -> None:
    state = _FakeState([{"id": 1, "title": "a"}], total=1)
    state._next_row = {"id": 5, "title": "new"}
    ctx = _Ctx(_Opts(paginate_by=None, ordering=("id",)))
    _run(state.apply_saved_row(ctx, object(), was_create=True))
    assert state.data[-1] == {"id": 5, "title": "new"}


def test_apply_saved_row_create_with_pagination_falls_back() -> None:
    state = _FakeState([{"id": 1, "title": "a"}], total=1)
    state._next_row = {"id": 5, "title": "new"}
    ctx = _Ctx(_Opts(paginate_by=20))
    patched = _run(state.apply_saved_row(ctx, object(), was_create=True))
    assert patched is False
    assert state.data == [{"id": 1, "title": "a"}]  # untouched


def test_apply_saved_row_update_missing_row_falls_back() -> None:
    state = _FakeState([{"id": 1, "title": "a"}], total=1)
    state._next_row = {"id": 99, "title": "ghost"}
    ctx = _Ctx(_Opts())
    patched = _run(state.apply_saved_row(ctx, object(), was_create=False))
    assert patched is False


def test_remove_row_removes_and_decrements() -> None:
    state = _FakeState([{"id": 1}, {"id": 2}, {"id": 3}], total=3)
    ctx = _Ctx(_Opts())
    assert state.remove_row(ctx, 2) is True
    assert [r["id"] for r in state.data] == [1, 3]
    assert state.total_count == 2


def test_remove_row_missing_pk_is_noop() -> None:
    state = _FakeState([{"id": 1}], total=1)
    ctx = _Ctx(_Opts())
    assert state.remove_row(ctx, 42) is False
    assert state.total_count == 1


def test_resolve_options_incremental_updates_default_false() -> None:
    class _State(AppState, ModelCRUDView):
        class Meta:
            serializer = IuNoteSerializer

    assert _State.get_options().incremental_updates is False


def test_resolve_options_incremental_updates_enabled() -> None:
    class _State(AppState, ModelCRUDView):
        incremental_updates = True

        class Meta:
            serializer = IuNoteSerializer

    assert _State.get_options().incremental_updates is True
