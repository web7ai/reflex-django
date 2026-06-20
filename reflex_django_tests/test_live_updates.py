"""Tests for reactive live model updates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest import mock

from django.db import models

from reflex_django.setup.conf import configure_django

configure_django()

from django.db.models.signals import post_delete, post_save  # noqa: E402

from reflex_django.live import (  # noqa: E402
    ACTION_CREATED,
    ACTION_DELETED,
    ACTION_UPDATED,
    ModelChange,
    is_live_model,
    live_broadcaster,
    model_label,
    register_live_model,
    unregister_live_model,
)
from reflex_django.live.broadcaster import LiveBroadcaster  # noqa: E402
from reflex_django.live.state import LiveListMixin  # noqa: E402
from reflex_django.state.mixins.list import ListMixin  # noqa: E402


class LiveWidget(models.Model):
    title = models.CharField(max_length=64)

    class Meta:
        app_label = "reflex_django_tests"


@dataclass
class _Opts:
    model: type[models.Model] = LiveWidget
    list_var: str = "data"
    total_count_var: str = "total_count"
    paginate_by: int | None = None
    ordering: tuple[str, ...] = ("-id",)


class _FakeQuerySet:
    def __init__(self, instance: Any | None) -> None:
        self.instance = instance
        self.pk = None

    def filter(self, **kwargs: Any):
        self.pk = kwargs.get("pk")
        return self

    async def afirst(self) -> Any | None:
        return self.instance


class _FakeLiveState(LiveListMixin, ListMixin):
    def __init__(self, rows: list[dict[str, Any]], instance: Any | None) -> None:
        self.data = list(rows)
        self.total_count = len(rows)
        self.instance = instance

    def get_options(self) -> _Opts:
        return _Opts()

    def get_scoped_queryset(self) -> _FakeQuerySet:
        return _FakeQuerySet(self.instance)

    async def serialize_instance(self, ctx: Any, instance: Any) -> dict[str, Any]:
        return {"id": instance.pk, "title": instance.title}


def test_model_label_uses_app_and_model_name() -> None:
    assert model_label(LiveWidget) == "reflex_django_tests.livewidget"


def test_register_live_model_is_idempotent_and_tracks_model() -> None:
    unregister_live_model(LiveWidget)
    assert is_live_model(LiveWidget) is False

    with mock.patch.object(post_save, "connect") as save_connect:
        with mock.patch.object(post_delete, "connect") as delete_connect:
            register_live_model(LiveWidget)
            register_live_model(LiveWidget)

    assert is_live_model(LiveWidget) is True
    save_connect.assert_called_once()
    delete_connect.assert_called_once()
    unregister_live_model(LiveWidget)


def test_registered_save_and_delete_signals_publish_changes() -> None:
    label = model_label(LiveWidget)
    instance = LiveWidget(id=7, title="signal")
    register_live_model(LiveWidget)
    try:
        with mock.patch.object(live_broadcaster(), "publish") as publish:
            post_save.send(sender=LiveWidget, instance=instance, created=True)
            post_save.send(sender=LiveWidget, instance=instance, created=False)
            post_delete.send(sender=LiveWidget, instance=instance)
    finally:
        unregister_live_model(LiveWidget)

    assert publish.mock_calls == [
        mock.call(ModelChange(label, ACTION_CREATED, 7)),
        mock.call(ModelChange(label, ACTION_UPDATED, 7)),
        mock.call(ModelChange(label, ACTION_DELETED, 7)),
    ]


def test_broadcaster_delivers_to_matching_subscribers() -> None:
    async def run() -> None:
        broadcaster = LiveBroadcaster()
        matching = broadcaster.subscribe("app.widget")
        other = broadcaster.subscribe("app.other")
        delivered = broadcaster.publish(ModelChange("app.widget", ACTION_UPDATED, 3))
        await asyncio.sleep(0)

        assert delivered == 1
        assert await matching.get() == ModelChange("app.widget", ACTION_UPDATED, 3)
        assert other.empty()
        broadcaster.unsubscribe("app.widget", matching)
        assert broadcaster.subscriber_count("app.widget") == 0

    asyncio.run(run())


def test_apply_live_change_patches_existing_row() -> None:
    async def run() -> None:
        instance = LiveWidget(id=2, title="updated")
        state = _FakeLiveState([{"id": 2, "title": "old"}], instance)
        await state.apply_live_change(
            ModelChange(model_label(LiveWidget), ACTION_UPDATED, 2)
        )
        assert state.data == [{"id": 2, "title": "updated"}]

    asyncio.run(run())


def test_apply_live_change_removes_deleted_or_out_of_scope_row() -> None:
    async def run() -> None:
        state = _FakeLiveState([{"id": 4, "title": "gone"}], None)
        await state.apply_live_change(
            ModelChange(model_label(LiveWidget), ACTION_UPDATED, 4)
        )
        assert state.data == []

        state = _FakeLiveState([{"id": 5, "title": "gone"}], None)
        await state.apply_live_change(
            ModelChange(model_label(LiveWidget), ACTION_DELETED, 5)
        )
        assert state.data == []

    asyncio.run(run())
