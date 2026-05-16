"""Resolved configuration for a concrete model state class."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import models

from reflex_django.serializers import ReflexDjangoModelSerializer
from reflex_django.state.constants import (
    DEFAULT_ERROR_VAR,
    DEFAULT_FIELD_ERRORS_VAR,
    DEFAULT_LIST_VAR,
    DEFAULT_ORDERING_VAR,
    DEFAULT_PAGE_COUNT_VAR,
    DEFAULT_SEARCH_VAR,
    DEFAULT_TOTAL_COUNT_VAR,
)
from reflex_django.state.fields import StateField, build_state_fields


def pluralize_model_name(name: str) -> str:
    """Pluralize a Django model class name (for ``Meta.list_var`` overrides)."""
    lower = name.lower()
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return lower + "es"
    return lower + "s"


def _get_attr(meta: type | None, state_cls: type, name: str, default: Any) -> Any:
    """Resolve config: subclass body → inner ``Meta`` → inherited default."""
    if name in state_cls.__dict__ and name not in ("Meta",):
        return state_cls.__dict__[name]
    if meta is not None and hasattr(meta, name):
        val = getattr(meta, name)
        if val is not None:
            return val
    inherited = getattr(state_cls, name, default)
    if inherited is not None:
        return inherited
    return default


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
    paginate_by: int | None
    max_page_size: int
    page_var: str
    page_size_var: str
    total_count_var: str
    page_count_var: str
    search_fields: tuple[str, ...]
    search_var: str
    allow_dynamic_ordering: bool
    ordering_var: str
    queryset_select_related: tuple[str, ...]
    queryset_prefetch: tuple[str, ...]
    use_canonical_api: bool


def _default_list_var(model_name: str, *, use_generic_var_names: bool) -> str:
    if use_generic_var_names:
        return DEFAULT_LIST_VAR
    return pluralize_model_name(model_name)


def resolve_options(
    serializer_cls: type[ReflexDjangoModelSerializer],
    meta: type | None,
    state_cls: type,
    *,
    use_generic_var_names: bool = False,
) -> ModelStateOptions:
    """Build :class:`ModelStateOptions` from serializer, ``Meta``, and class attrs.

    When ``use_generic_var_names`` is true (``ModelState`` subclasses), unset
    ``Meta`` keys default to ``data``, ``error``, ``search``, etc. Legacy
    ``ModelCRUDView`` without ``ModelState`` keeps pluralized list names.
    """
    from reflex_django.state.backends.django import DjangoORMBackend

    model = serializer_cls.get_model()
    model_name = model.__name__
    list_var = str(
        _get_attr(meta, state_cls, "list_var", None)
        or _default_list_var(model_name, use_generic_var_names=use_generic_var_names)
    )
    error_var = str(
        _get_attr(meta, state_cls, "error_var", None)
        or (DEFAULT_ERROR_VAR if use_generic_var_names else f"{list_var}_error")
    )
    structured_errors = bool(_get_attr(meta, state_cls, "structured_errors", False))
    field_errors_var = (
        str(
            _get_attr(meta, state_cls, "field_errors_var", None)
            or (
                DEFAULT_FIELD_ERRORS_VAR
                if use_generic_var_names
                else f"{list_var}_field_errors"
            )
        )
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
    paginate_raw = _get_attr(meta, state_cls, "paginate_by", None)
    paginate_by = int(paginate_raw) if paginate_raw is not None else None
    max_page_size = int(_get_attr(meta, state_cls, "max_page_size", 100))
    page_var = str(_get_attr(meta, state_cls, "page_var", "page"))
    page_size_var = str(_get_attr(meta, state_cls, "page_size_var", "page_size"))
    total_count_var = str(
        _get_attr(meta, state_cls, "total_count_var", None)
        or (
            DEFAULT_TOTAL_COUNT_VAR
            if use_generic_var_names
            else f"{list_var}_total_count"
        )
    )
    page_count_var = str(
        _get_attr(meta, state_cls, "page_count_var", None)
        or (
            DEFAULT_PAGE_COUNT_VAR
            if use_generic_var_names
            else f"{list_var}_page_count"
        )
    )
    search_fields = tuple(_get_attr(meta, state_cls, "search_fields", ()) or ())
    search_var = str(
        _get_attr(meta, state_cls, "search_var", None)
        or (DEFAULT_SEARCH_VAR if use_generic_var_names else f"{list_var}_search")
    )
    allow_dynamic_ordering = bool(
        _get_attr(meta, state_cls, "allow_dynamic_ordering", False)
    )
    ordering_var = str(
        _get_attr(meta, state_cls, "ordering_var", None)
        or (DEFAULT_ORDERING_VAR if use_generic_var_names else f"{list_var}_ordering")
    )
    use_canonical_api = bool(_get_attr(meta, state_cls, "use_canonical_api", True))

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
        paginate_by=paginate_by,
        max_page_size=max_page_size,
        page_var=page_var,
        page_size_var=page_size_var,
        total_count_var=total_count_var,
        page_count_var=page_count_var,
        search_fields=search_fields,
        search_var=search_var,
        allow_dynamic_ordering=allow_dynamic_ordering,
        ordering_var=ordering_var,
        queryset_select_related=queryset_select_related,
        queryset_prefetch=queryset_prefetch,
        use_canonical_api=use_canonical_api,
    )


__all__ = ["ModelStateOptions", "pluralize_model_name", "resolve_options"]
