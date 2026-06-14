"""Meta resolution helpers for model state assembly."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import reflex as rx
from django.db import models

from reflex_django.state.serializer_factory import build_serializer_from_fields
from reflex_django.state.views.crud import ModelCRUDView
from reflex_django.state.views.list import ModelListView

_MODEL_STATE_BASES = (ModelCRUDView, ModelListView)


def bind_event(
    handler: Any,
    *,
    login_required: bool,
) -> Any:
    if login_required:
        from reflex_django.auth.decorators import login_required

        return rx.event(login_required(handler))
    return rx.event(handler)


def _is_model_state_origin(origin: Any) -> bool:
    if not isinstance(origin, type):
        return False
    if origin.__name__ != "ModelState":
        return False
    mod = getattr(origin, "__module__", "") or ""
    return mod.endswith(".model_state") or mod.endswith(".generic")


def _model_from_model_state_base(base: Any) -> type[models.Model] | None:
    """Resolve concrete model from ``ModelState[Note]`` (a ``GenericAlias`` base)."""
    origin = getattr(base, "__origin__", None)
    if origin is None or not _is_model_state_origin(origin):
        return None
    args = getattr(base, "__args__", ())
    if not args:
        return None
    candidate = args[0]
    if isinstance(candidate, type) and issubclass(candidate, models.Model):
        return candidate
    return None


def _resolve_model_from_bases(bases: tuple[Any, ...]) -> type[models.Model] | None:
    for base in bases:
        found = _model_from_model_state_base(base)
        if found is not None:
            return found
    return None


def needs_assembly(bases: tuple[Any, ...]) -> bool:
    for b in bases:
        if isinstance(b, type) and issubclass(b, _MODEL_STATE_BASES):
            return True
        origin = getattr(b, "__origin__", None)
        if isinstance(origin, type) and issubclass(origin, _MODEL_STATE_BASES):
            return True
    return False


def uses_model_state_base(bases: tuple[Any, ...]) -> bool:
    """True when a base is ``ModelState`` or ``ModelState[SomeModel]``."""
    for b in bases:
        origin = getattr(b, "__origin__", None)
        if origin is not None and _is_model_state_origin(origin):
            return True
        if isinstance(b, type) and _is_model_state_origin(b):
            return True
    return False


def _reactive_var_on_base(bases: tuple[Any, ...], name: str) -> bool:
    """True when a ``ModelState`` ancestor already declares a reactive var name."""
    for base in bases:
        if isinstance(base, type) and name in getattr(base, "__annotations__", {}):
            return True
    return False


def inject_var_default(
    namespace: dict[str, Any],
    annotations: dict[str, Any],
    bases: tuple[Any, ...],
    name: str,
    annotation: Any,
    default: Any,
) -> None:
    """Add a state var annotation; skip plain defaults that shadow ``ModelState`` vars."""
    if name in namespace:
        return
    annotations[name] = annotation
    if not _reactive_var_on_base(bases, name):
        namespace[name] = default


def extract_model_and_fields(
    namespace: dict[str, Any],
    bases: tuple[Any, ...],
) -> tuple[type[models.Model] | None, Sequence[str] | None, tuple[str, ...]]:
    model = namespace.get("model")
    fields = namespace.get("fields")
    read_only: tuple[str, ...] = tuple(namespace.get("read_only_fields", ()) or ())
    if model is None:
        model = _resolve_model_from_bases(bases)
    orig_bases = namespace.get("__orig_bases__")
    if model is None and orig_bases:
        model = _resolve_model_from_bases(tuple(orig_bases))
    meta = namespace.get("Meta")
    if meta is not None:
        if model is None:
            model = getattr(meta, "model", None)
        if not fields:
            fields = getattr(meta, "fields", None)
        meta_ro = getattr(meta, "read_only_fields", None)
        if meta_ro:
            read_only = tuple(meta_ro) + read_only
    for base in bases:
        if isinstance(base, type):
            if model is None:
                candidate = getattr(base, "model", None)
                if isinstance(candidate, type) and issubclass(candidate, models.Model):
                    model = candidate
            if not fields:
                candidate_fields = getattr(base, "fields", None)
                if candidate_fields:
                    fields = candidate_fields
            if not read_only:
                base_ro = getattr(base, "read_only_fields", None)
                if base_ro:
                    read_only = tuple(base_ro)
    return model, fields, read_only


def resolve_serializer(
    namespace: dict[str, Any],
    bases: tuple[type, ...],
) -> type | None:
    meta = namespace.get("Meta")
    if meta is not None:
        ser = getattr(meta, "serializer", None)
        if ser is not None:
            return ser
    if "serializer_class" in namespace:
        return namespace["serializer_class"]
    for base in bases:
        ser = getattr(base, "serializer_class", None)
        if ser is not None:
            return ser
    model, fields, read_only = extract_model_and_fields(namespace, bases)
    if model is not None and fields:
        return build_serializer_from_fields(
            model,
            fields,
            read_only_fields=read_only,
        )
    return None
