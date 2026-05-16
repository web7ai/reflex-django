"""Public state API: :class:`ModelState` and :class:`AppState`."""

from __future__ import annotations

from typing import Any

from reflex_django.state._model_crud import (
    ModelStateConfig,
    inject_model_state_namespace,
    maybe_inject_model_state,
    populate_model_state_class,
    register_state_class,
    resolve_model_state_config,
)
from reflex_django.state.model_state import ModelState

__all__ = [
    "AppState",
    "ModelState",
    "ModelStateConfig",
    "inject_model_state_namespace",
    "maybe_inject_model_state",
    "populate_model_state_class",
    "register_state_class",
    "resolve_model_state_config",
]


def __getattr__(name: str) -> Any:
    if name == "AppState":
        from reflex_django.states import AppState

        return AppState
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
