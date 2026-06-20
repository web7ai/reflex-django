"""Dev-only inspection primitives: per-event tier, timing, and query capture.

Enable with ``RX_DEVTOOLS=1`` (env) or ``RX_DEVTOOLS = True`` in Django settings.
Everything here is a no-op unless devtools are enabled, so it is safe to leave
the bridge hook installed in development builds.
"""

from __future__ import annotations

import contextvars
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

_inspection_var: contextvars.ContextVar[EventInspection | None] = (
    contextvars.ContextVar("reflex_django.devtools.inspection", default=None)
)
_capture_handle_var: contextvars.ContextVar[tuple[Any, Any] | None] = (
    contextvars.ContextVar("reflex_django.devtools.capture_handle", default=None)
)
_capture_start_var: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "reflex_django.devtools.capture_start", default=None
)


@dataclass(frozen=True)
class QueryRecord:
    """One captured SQL statement and its wall-clock duration."""

    sql: str
    duration_ms: float


@dataclass
class EventInspection:
    """Mutable per-event diagnostics record."""

    tier: str = ""
    handler: str = ""
    duration_ms: float = 0.0
    queries: list[QueryRecord] = field(default_factory=list)

    @property
    def query_count(self) -> int:
        return len(self.queries)

    @property
    def total_query_ms(self) -> float:
        return sum(q.duration_ms for q in self.queries)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "handler": self.handler,
            "duration_ms": round(self.duration_ms, 2),
            "query_count": self.query_count,
            "total_query_ms": round(self.total_query_ms, 2),
        }


def devtools_enabled() -> bool:
    """Return whether dev inspectors are turned on (env or Django setting)."""
    env = os.environ.get("RX_DEVTOOLS")
    if env is not None:
        return env.strip().lower() in {"1", "true", "yes", "on"}
    try:
        from django.conf import settings

        return bool(getattr(settings, "RX_DEVTOOLS", False))
    except Exception:
        return False


def current_inspection() -> EventInspection | None:
    """Return the inspection record bound to the current event, if any."""
    return _inspection_var.get()


def begin_inspection(*, tier: str = "", handler: str = "") -> EventInspection:
    """Start a fresh inspection record for the current async task."""
    record = EventInspection(tier=tier, handler=handler)
    _inspection_var.set(record)
    return record


def end_inspection() -> EventInspection | None:
    """Detach and return the current inspection record."""
    record = _inspection_var.get()
    _inspection_var.set(None)
    return record


def record_query(sql: str, duration_ms: float) -> None:
    """Append a captured query to the active inspection (no-op when inactive)."""
    record = _inspection_var.get()
    if record is not None:
        record.queries.append(QueryRecord(sql=sql, duration_ms=duration_ms))


def _make_query_wrapper() -> Any:
    def _wrapper(execute: Any, sql: Any, params: Any, many: Any, context: Any) -> Any:
        record = _inspection_var.get()
        if record is None:
            return execute(sql, params, many, context)
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            record_query(str(sql), (time.perf_counter() - start) * 1000.0)

    return _wrapper


def start_event_capture(
    *,
    tier: str = "",
    handler: str = "",
    using: str = "default",
) -> EventInspection:
    """Begin inspecting the current event and install a SQL query wrapper.

    Pairs with :func:`finish_event_capture`. Exception-safe: failures to install
    the query wrapper still produce a timing/tier record.
    """
    record = begin_inspection(tier=tier, handler=handler)
    _capture_start_var.set(time.perf_counter())
    try:
        from django.db import connections

        connection = connections[using]
        wrapper = _make_query_wrapper()
        connection.execute_wrappers.append(wrapper)
        _capture_handle_var.set((connection, wrapper))
    except Exception:
        _capture_handle_var.set(None)
    return record


def finish_event_capture() -> EventInspection | None:
    """Stop query capture, finalize timing, and return the inspection record."""
    handle = _capture_handle_var.get()
    _capture_handle_var.set(None)
    if handle is not None:
        connection, wrapper = handle
        try:
            connection.execute_wrappers.remove(wrapper)
        except Exception:
            pass
    record = _inspection_var.get()
    start = _capture_start_var.get()
    _capture_start_var.set(None)
    if record is not None and start is not None:
        record.duration_ms = (time.perf_counter() - start) * 1000.0
    return end_inspection()


@contextmanager
def capture_queries(using: str = "default") -> Iterator[EventInspection]:
    """Capture SQL run on connection *using* into a fresh inspection record.

    Best-effort for async ORM (which may run on a different connection); fully
    reliable for synchronous queries executed inside the block.
    """
    from django.db import connections

    record = begin_inspection(tier=getattr(current_inspection(), "tier", "") or "")
    start = time.perf_counter()
    connection = connections[using]
    wrapper = _make_query_wrapper()
    try:
        with connection.execute_wrapper(wrapper):
            yield record
    finally:
        record.duration_ms = (time.perf_counter() - start) * 1000.0
        end_inspection()


__all__ = [
    "EventInspection",
    "QueryRecord",
    "begin_inspection",
    "capture_queries",
    "current_inspection",
    "devtools_enabled",
    "end_inspection",
    "finish_event_capture",
    "record_query",
    "start_event_capture",
]
