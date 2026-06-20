"""Combine the per-event inspection with the bound request into one summary."""

from __future__ import annotations

from typing import Any

from reflex_django.devtools.inspector import current_inspection
from reflex_django.devtools.snapshot import bound_request_summary


def collect_inspection_summary() -> dict[str, Any]:
    """Return a flat summary of the current event (tier, queries, user).

    Safe to call from inside an ``@rx.event`` handler, where the bridge request
    and inspection record are still bound to the active task.
    """
    request = bound_request_summary()
    inspection = current_inspection()
    summary: dict[str, Any] = {
        "tier": inspection.tier if inspection else "",
        "handler": inspection.handler if inspection else "",
        "duration_ms": round(inspection.duration_ms, 2) if inspection else 0.0,
        "query_count": inspection.query_count if inspection else 0,
        "total_query_ms": (round(inspection.total_query_ms, 2) if inspection else 0.0),
        "user": request["user"],
        "authenticated": request["authenticated"],
        "session_key": request["session_key"],
        "path": request["path"],
    }
    return summary


__all__ = ["collect_inspection_summary"]
