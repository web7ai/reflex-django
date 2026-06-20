"""Tests for the dev inspectors (tier/timing/query capture, snapshot, overlay)."""

from __future__ import annotations

import reflex as rx

from reflex_django.setup.conf import configure_django

configure_django()

from django.db import connection  # noqa: E402

from reflex_django.devtools import (  # noqa: E402
    bound_request_summary,
    capture_queries,
    collect_inspection_summary,
    current_inspection,
    dev_inspector_overlay,
    devtools_enabled,
    state_tree_snapshot,
)
from reflex_django.devtools.inspector import (  # noqa: E402
    EventInspection,
    QueryRecord,
    begin_inspection,
    end_inspection,
    finish_event_capture,
    start_event_capture,
)


def test_devtools_enabled_env(monkeypatch) -> None:
    monkeypatch.delenv("RX_DEVTOOLS", raising=False)
    assert devtools_enabled() is False
    monkeypatch.setenv("RX_DEVTOOLS", "1")
    assert devtools_enabled() is True
    monkeypatch.setenv("RX_DEVTOOLS", "off")
    assert devtools_enabled() is False


def test_event_inspection_as_dict() -> None:
    insp = EventInspection(tier="smart", handler="State.go")
    insp.queries.append(QueryRecord("SELECT 1", 2.0))
    data = insp.as_dict()
    assert data["tier"] == "smart"
    assert data["query_count"] == 1
    assert data["total_query_ms"] == 2.0


def test_capture_queries_records_sql() -> None:
    with capture_queries() as insp:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    assert insp.query_count >= 1
    assert insp.duration_ms >= 0.0
    assert any("SELECT 1" in q.sql for q in insp.queries)
    # capture is detached after the block
    assert current_inspection() is None


def test_start_finish_event_capture() -> None:
    start_event_capture(tier="full", handler="State.save")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    record = finish_event_capture()
    assert record is not None
    assert record.tier == "full"
    assert record.handler == "State.save"
    assert record.query_count >= 1
    assert current_inspection() is None


class _Leaf:
    def __init__(self) -> None:
        self.vars = {"count": None, "label": None}
        self.count = 3
        self.label = "leaf"
        self.substates: dict = {}


class _Root:
    def __init__(self, leaf: _Leaf) -> None:
        self.vars = {"title": None, "_secret": None}
        self.title = "hi"
        self._secret = "nope"
        self.substates = {"leaf": leaf}


def test_state_tree_snapshot() -> None:
    snap = state_tree_snapshot(_Root(_Leaf()))
    assert snap["name"] == "_Root"
    assert snap["vars"] == {"title": "hi"}  # underscore var excluded
    assert len(snap["substates"]) == 1
    leaf = snap["substates"][0]
    assert leaf["name"] == "_Leaf"
    assert leaf["vars"] == {"count": 3, "label": "leaf"}


def test_bound_request_summary_no_request() -> None:
    summary = bound_request_summary()
    assert summary["bound"] is False
    assert summary["authenticated"] is False


def test_collect_inspection_summary_uses_active_inspection() -> None:
    begin_inspection(tier="smart", handler="State.go")
    try:
        summary = collect_inspection_summary()
        assert summary["tier"] == "smart"
        assert summary["handler"] == "State.go"
        assert summary["authenticated"] is False
    finally:
        end_inspection()


def test_collect_inspection_summary_without_inspection() -> None:
    end_inspection()
    summary = collect_inspection_summary()
    assert summary["tier"] == ""
    assert summary["query_count"] == 0


def test_dev_inspector_overlay_builds_component() -> None:
    component = dev_inspector_overlay()
    assert isinstance(component, rx.Component)
