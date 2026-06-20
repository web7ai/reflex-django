"""Serializable snapshots of the Reflex substate tree and the bound Django request."""

from __future__ import annotations

from typing import Any

_JSONISH = (str, int, float, bool)


def _jsonish(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, _JSONISH):
        return value
    if depth > 3:
        return repr(value)[:120]
    if isinstance(value, dict):
        return {
            str(k): _jsonish(v, depth=depth + 1) for k, v in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple)):
        return [_jsonish(v, depth=depth + 1) for v in list(value)[:50]]
    return repr(value)[:120]


def state_tree_snapshot(state: Any, *, max_depth: int = 4) -> dict[str, Any]:
    """Return a nested ``{name, vars, substates}`` snapshot of *state*.

    Only public (non underscore-prefixed) reactive vars with JSON-friendly
    values are included. Defensive against Reflex internals changing shape.
    """
    return _snapshot(state, depth=0, max_depth=max_depth)


def _snapshot(state: Any, *, depth: int, max_depth: int) -> dict[str, Any]:
    node: dict[str, Any] = {
        "name": type(state).__name__,
        "vars": {},
        "substates": [],
    }
    try:
        var_names = list(getattr(state, "vars", {}) or {})
    except Exception:
        var_names = []
    for name in var_names:
        if name.startswith("_"):
            continue
        try:
            value = getattr(state, name)
        except Exception:
            continue
        if callable(value):
            continue
        node["vars"][name] = _jsonish(value)

    if depth < max_depth:
        try:
            substates = getattr(state, "substates", {}) or {}
        except Exception:
            substates = {}
        for sub in substates.values():
            node["substates"].append(
                _snapshot(sub, depth=depth + 1, max_depth=max_depth)
            )
    return node


def bound_request_summary() -> dict[str, Any]:
    """Summarize the Django request/user bound to the current event (if any)."""
    summary: dict[str, Any] = {
        "bound": False,
        "user": "AnonymousUser",
        "authenticated": False,
        "session_key": "",
        "path": "",
    }
    try:
        from reflex_django.bridge.context import current_request
    except Exception:
        return summary

    request = current_request()
    if request is None:
        return summary
    summary["bound"] = True
    user = getattr(request, "user", None)
    if user is not None:
        summary["user"] = str(getattr(user, "username", "") or user)
        summary["authenticated"] = bool(getattr(user, "is_authenticated", False))
    session = getattr(request, "session", None)
    summary["session_key"] = getattr(session, "session_key", "") or ""
    summary["path"] = getattr(request, "path", "") or ""
    return summary


__all__ = ["bound_request_summary", "state_tree_snapshot"]
