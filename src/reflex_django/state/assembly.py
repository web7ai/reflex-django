"""Thin re-export shim — implementation lives in :mod:`reflex_django.state.assembly`."""

from reflex_django.state.assembly import (
    assemble_model_state_namespace,
    bind_event,
    inject_simple_var_setters,
    maybe_assemble_model_state,
    maybe_inject_var_setters,
    register_state_class,
)

__all__ = [
    "assemble_model_state_namespace",
    "bind_event",
    "inject_simple_var_setters",
    "maybe_assemble_model_state",
    "maybe_inject_var_setters",
    "register_state_class",
]
