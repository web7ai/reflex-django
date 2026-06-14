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


def resolve_state_root(state: Any) -> Any | None:
    """Return the root state for *state*, or ``None`` when unusable."""
    if is_unusable_state(state):
        return None
    try:
        root = state._get_root_state()  # noqa: SLF001
    except (AttributeError, TypeError):
        root = state
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
    root = resolve_state_root(state)
    if root is None:
        return None

    seen: set[int] = set()
    node: Any = root
    hops = max_hops
    while node is not None and id(node) not in seen and hops > 0:
        hops -= 1
        seen.add(id(node))
        if is_unusable_state(node):
            break
        result = predicate(node)
        if result is not None:
            return result
        parent = getattr(node, "parent_state", None)
        if is_unusable_state(parent):
            break
        node = parent
    return None


__all__ = [
    "find_in_parent_chain",
    "is_unusable_state",
    "resolve_state_root",
    "walk_substates_dfs",
]