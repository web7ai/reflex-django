"""Public state API: model CRUD CBVs and :class:`AppState`."""

from __future__ import annotations

from typing import Any

from reflex_django.state.assembly import (
    assemble_model_state_namespace,
    bind_event,
    maybe_assemble_model_state,
    register_state_class,
)
from reflex_django.state.base import ActionContext, BaseModelState
from reflex_django.state.fields import (
    BoolStateField,
    IntStateField,
    StateField,
    StrStateField,
    build_state_fields,
    state_field_for_name,
)
from reflex_django.state.model_state import ModelCRUDView, ModelState
from reflex_django.state.options import ModelStateOptions, resolve_options
from reflex_django.state.serializer_factory import (
    build_serializer_from_fields,
    validate_model_fields,
)
from reflex_django.state.request import DjangoStateRequest
from reflex_django.state.views.list import ModelListView
from reflex_django.state.views.meta import ModelCRUDMeta, ModelListMeta

__all__ = [
    "ActionContext",
    "AppState",
    "BaseModelState",
    "BoolStateField",
    "DjangoStateRequest",
    "IntStateField",
    "ModelCRUDMeta",
    "ModelCRUDView",
    "ModelListMeta",
    "ModelListView",
    "ModelState",
    "ModelStateOptions",
    "StateField",
    "StrStateField",
    "assemble_model_state_namespace",
    "bind_event",
    "build_serializer_from_fields",
    "build_state_fields",
    "maybe_assemble_model_state",
    "register_state_class",
    "resolve_options",
    "state_field_for_name",
    "validate_model_fields",
]


def __getattr__(name: str) -> Any:
    if name == "AppState":
        from reflex_django.states import AppState

        return AppState
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
