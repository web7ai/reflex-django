"""Dev-only inspectors: bridge-tier overlay, per-event query/timing, state tree.

Enable with ``RX_DEVTOOLS=1`` (env) or ``RX_DEVTOOLS = True`` in settings. The
``dev_inspector_overlay`` component and ``DjangoDevToolsState`` are imported
lazily so importing this package stays cheap and does not register a Reflex
state unless the overlay is actually used.
"""

from __future__ import annotations

from typing import Any

from reflex_django.devtools.inspector import (
    EventInspection,
    QueryRecord,
    capture_queries,
    current_inspection,
    devtools_enabled,
    finish_event_capture,
    start_event_capture,
)
from reflex_django.devtools.report import collect_inspection_summary
from reflex_django.devtools.snapshot import bound_request_summary, state_tree_snapshot

__all__ = [
    "DjangoDevToolsState",
    "EventInspection",
    "QueryRecord",
    "bound_request_summary",
    "capture_queries",
    "collect_inspection_summary",
    "current_inspection",
    "dev_inspector_overlay",
    "devtools_enabled",
    "finish_event_capture",
    "start_event_capture",
    "state_tree_snapshot",
]


def __getattr__(name: str) -> Any:
    if name in ("DjangoDevToolsState", "dev_inspector_overlay"):
        from reflex_django.devtools import overlay

        return getattr(overlay, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
