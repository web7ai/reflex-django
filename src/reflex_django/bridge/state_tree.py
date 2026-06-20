"""Shared Reflex state-tree traversal helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

_T = TypeVar("_T")


def is_unusable_state(state: Any) -> bool:
    """Return whether *state* should be skipped (``None`` or a test ``Mock``)."""
    if state is None:
        return True
    from unittest.mock import Mock

    return isinstance(state, Mock)


_PROXY_TYPE_NAMES = frozenset({"StateProxy", "ReadOnlyStateProxy"})


def unwrap_state_proxy(state: Any) -> Any:
    """Return the inner state when *state* is a Reflex background-task proxy."""
    wrapped = getattr(state, "__wrapped__", None)
    if wrapped is not None and type(state).__name__ in _PROXY_TYPE_NAMES:
        return wrapped
    return state


def _safe_parent_state(state: Any) -> Any | None:
    """Return ``parent_state`` without raising on immutable background proxies."""
    try:
        parent = getattr(state, "parent_state", None)
    except Exception as exc:
        if type(exc).__name__ == "ImmutableStateError":
            return None
        raise
    if is_unusable_state(parent):
        return None
    return unwrap_state_proxy(parent)


def resolve_state_root(state: Any) -> Any | None:
    """Return the root state for *state*, or ``None`` when unusable."""
    if is_unusable_state(state):
        return None
    state = unwrap_state_proxy(state)
    try:
        root = state._get_root_state()  # noqa: SLF001
    except (AttributeError, TypeError):
        root = state
    except Exception as exc:
        if type(exc).__name__ == "ImmutableStateError":
            root = state
        else:
            raise
    root = unwrap_state_proxy(root)
    if is_unusable_state(root):
        return None
    return root


def walk_substates_dfs(
    state: Any,
    visitor: Callable[[Any], None],
    *,
    max_nodes: int = 4096,
) -> None:
    """Depth-first visit of *state* and every descendant substate."""
    root = resolve_state_root(state)
    if root is None:
        return

    seen: set[int] = set()
    remaining = max_nodes

    def visit(node: Any) -> None:
        nonlocal remaining
        if is_unusable_state(node) or id(node) in seen or remaining <= 0:
            return
        remaining -= 1
        seen.add(id(node))
        visitor(node)
        substates = getattr(node, "substates", None) or {}
        if isinstance(substates, dict):
            for child in substates.values():
                visit(child)

    visit(root)


def find_in_parent_chain(
    state: Any,
    predicate: Callable[[Any], _T | None],
    *,
    max_hops: int = 64,
) -> _T | None:
    """Walk *state* and ancestors via ``parent_state``; return the first match."""
    if is_unusable_state(state):
        return None

    seen: set[int] = set()
    node: Any = unwrap_state_proxy(state)
    hops = max_hops
    while node is not None and id(node) not in seen and hops > 0:
        hops -= 1
        seen.add(id(node))
        if is_unusable_state(node):
            break
        result = predicate(node)
        if result is not None:
            return result
        node = _safe_parent_state(node)
    return None


__all__ = [
    "find_in_parent_chain",
    "is_unusable_state",
    "resolve_state_root",
    "unwrap_state_proxy",
    "walk_substates_dfs",
]
