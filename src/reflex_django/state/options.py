"""Resolved configuration for a concrete model state class."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import models

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.fields import StateField, build_state_fields


def _pluralize(name: str) -> str:
    lower = name.lower()
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return lower + "es"
    return lower + "s"


def _get_attr(meta: type | None, state_cls: type, name: str, default: Any) -> Any:
    if hasattr(state_cls, name) and name not in ("Meta",):
        val = getattr(state_cls, name, None)
        if val is not None and name in state_cls.__dict__:
            return val
    if meta is not None and hasattr(meta, name):
        return getattr(meta, name)
    return getattr(state_cls, name, default)


@dataclass(frozen=True)
class ModelStateOptions:
    """Immutable options resolved once per state class."""

    serializer_class: type[ReflexDjangoModelSerializer]
    model: type[models.Model]
    list_var: str
    error_var: str
    field_errors_var: str | None
    editing_var: str
    state_fields: tuple[StateField[Any, Any], ...]
    ordering: tuple[str, ...]
    required_fields: frozenset[str]
    read_only_fields: frozenset[str]
    exclude_from_row: frozenset[str]
    on_load_event: str
    save_event: str
    delete_event: str
    cancel_event: str
    load_method: str
    login_required_actions: frozenset[str]
    permission_classes: tuple[type, ...]
    backend_class: type
    structured_errors: bool
    run_model_validation: bool
    load_context_processors: bool
    reset_after_save: bool
    form_reset_var: str | None
    use_form_submit: bool
    queryset_select_related: tuple[str, ...]
    queryset_prefetch: tuple[str, ...]


def resolve_options(
    serializer_cls: type[ReflexDjangoModelSerializer],
    meta: type | None,
    state_cls: type,
) -> ModelStateOptions:
    """Build :class:`ModelStateOptions` from serializer, ``Meta``, and class attrs."""
    from reflex_django.state.backends.django import DjangoORMBackend

    model = serializer_cls.get_model()
    model_name = model.__name__
    list_var = _get_attr(meta, state_cls, "list_var", None) or _pluralize(model_name)
    error_var = _get_attr(meta, state_cls, "error_var", None) or f"{list_var}_error"
    structured_errors = bool(_get_attr(meta, state_cls, "structured_errors", False))
    field_errors_var = (
        _get_attr(meta, state_cls, "field_errors_var", None) or f"{list_var}_field_errors"
        if structured_errors
        else None
    )
    editing_var = _get_attr(meta, state_cls, "editing_var", "editing_id")
    state_read_only = frozenset(_get_attr(meta, state_cls, "read_only_fields", ()) or ())
    read_only = serializer_cls.get_read_only_field_names(
        extra_read_only=state_read_only,
    )
    explicit_state_fields = _get_attr(meta, state_cls, "state_fields", None)
    if explicit_state_fields is not None:
        field_names = tuple(explicit_state_fields)
    else:
        field_names = serializer_cls.writable_field_names(
            read_only_fields=read_only,
        )
    required_raw = _get_attr(meta, state_cls, "required_fields", None)
    if required_raw is not None:
        required_fields = frozenset(required_raw)
    elif field_names:
        required_fields = frozenset({field_names[0]})
    else:
        required_fields = frozenset()
    ordering = tuple(_get_attr(meta, state_cls, "ordering", ("-created_at",)))
    model_lower = model._meta.model_name
    on_load_event = _get_attr(meta, state_cls, "on_load_event", None) or f"on_load_{list_var}"
    save_event = _get_attr(meta, state_cls, "save_event", None) or f"save_{model_lower}"
    delete_event = _get_attr(meta, state_cls, "delete_event", None) or f"delete_{model_lower}"
    cancel_event = _get_attr(meta, state_cls, "cancel_event", "cancel_edit")
    load_method = f"_load_{list_var}"
    exclude_from_row = frozenset(_get_attr(meta, state_cls, "exclude_from_row", ()) or ())
    from reflex_django.state.constants import DEFAULT_LOGIN_REQUIRED_ACTIONS

    login_required_actions = frozenset(
        _get_attr(meta, state_cls, "login_required_actions", None)
        or DEFAULT_LOGIN_REQUIRED_ACTIONS
    )
    permission_classes = tuple(
        _get_attr(meta, state_cls, "permission_classes", ()) or ()
    )
    backend_class = _get_attr(meta, state_cls, "backend_class", DjangoORMBackend)
    run_model_validation = bool(_get_attr(meta, state_cls, "run_model_validation", False))
    load_context_processors = bool(
        _get_attr(meta, state_cls, "load_context_processors", True)
    )
    reset_after_save = bool(_get_attr(meta, state_cls, "reset_after_save", True))
    form_reset_var = _get_attr(meta, state_cls, "form_reset_var", "form_reset_key")
    use_form_submit = bool(_get_attr(meta, state_cls, "use_form_submit", False))
    queryset_select_related = tuple(
        _get_attr(meta, state_cls, "queryset_select_related", ()) or ()
    )
    queryset_prefetch = tuple(_get_attr(meta, state_cls, "queryset_prefetch", ()) or ())

    state_fields = build_state_fields(
        field_names,
        required_fields=required_fields,
    )

    return ModelStateOptions(
        serializer_class=serializer_cls,
        model=model,
        list_var=list_var,
        error_var=error_var,
        field_errors_var=field_errors_var,
        editing_var=editing_var,
        state_fields=state_fields,
        ordering=ordering,
        required_fields=required_fields,
        read_only_fields=read_only,
        exclude_from_row=exclude_from_row,
        on_load_event=on_load_event,
        save_event=save_event,
        delete_event=delete_event,
        cancel_event=cancel_event,
        load_method=load_method,
        login_required_actions=login_required_actions,
        permission_classes=permission_classes,
        backend_class=backend_class,
        structured_errors=structured_errors,
        run_model_validation=run_model_validation,
        load_context_processors=load_context_processors,
        reset_after_save=reset_after_save,
        form_reset_var=form_reset_var,
        use_form_submit=use_form_submit,
        queryset_select_related=queryset_select_related,
        queryset_prefetch=queryset_prefetch,
    )


__all__ = ["ModelStateOptions", "resolve_options"]
