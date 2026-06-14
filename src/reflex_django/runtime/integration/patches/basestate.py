"""Strip Django request artefacts from Reflex state serialization."""

from __future__ import annotations

from typing import Any

_DJANGO_TRANSIENT_STATE_ATTRS: tuple[str, ...] = (
    "_rx_request_wrapper",
    "_rx_response",
)


def _patch_basestate_getstate() -> None:
    """Strip non-picklable Django wrappers from state before Reflex pickles it."""
    try:
        from reflex.state import BaseState
    except ImportError:
        return

    if getattr(BaseState, "_reflex_django_getstate_patched", False):
        return

    original_getstate = BaseState.__getstate__

    def patched_getstate(self: Any) -> dict[str, Any]:
        state = original_getstate(self)
        if not isinstance(state, dict):
            return state
        for transient in _DJANGO_TRANSIENT_STATE_ATTRS:
            state.pop(transient, None)
        return state

    BaseState.__getstate__ = patched_getstate  # type: ignore[method-assign]
    BaseState._reflex_django_getstate_patched = True
    BaseState._reflex_django_getstate_original = original_getstate
