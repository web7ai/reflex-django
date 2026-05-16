"""Build declarative :class:`ModelState` subclasses from serializer metadata."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import reflex as rx
from django.db import models

from reflex_django.auth.decorators import login_required
from reflex_django.auth.shortcuts import require_login_user
from reflex_django.serializers import ReflexDjangoModelSerializer


def _pluralize(name: str) -> str:
    lower = name.lower()
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return lower + "es"
    return lower + "s"


@dataclass(frozen=True)
class ModelStateConfig:
    """Resolved options for a concrete :class:`ModelState` subclass."""

    serializer_cls: type[ReflexDjangoModelSerializer]
    model: type[models.Model]
    list_var: str
    error_var: str
    form_fields: tuple[str, ...]
    owner_field: str | None
    ordering: tuple[str, ...]
    required_fields: tuple[str, ...]
    read_only_fields: frozenset[str]
    on_load_event: str
    save_event: str
    delete_event: str
    load_method: str
    exclude_from_row: frozenset[str]


def resolve_model_state_config(
    serializer_cls: type[ReflexDjangoModelSerializer],
    meta: type,
) -> ModelStateConfig:
    """Build :class:`ModelStateConfig` from ``ModelState.Meta`` and a serializer."""
    model = serializer_cls.get_model()
    model_name = model.__name__
    list_var = getattr(meta, "list_var", None) or _pluralize(model_name)
    error_var = getattr(meta, "error_var", None) or f"{list_var}_error"
    owner_field = getattr(meta, "owner_field", "user")
    state_read_only = frozenset(getattr(meta, "read_only_fields", ()) or ())
    read_only = serializer_cls.get_read_only_field_names(
        owner_field=owner_field,
        extra_read_only=state_read_only,
    )
    explicit_form = getattr(meta, "form_fields", None)
    form_fields = serializer_cls.writable_field_names(
        owner_field=owner_field,
        read_only_fields=read_only,
        form_fields=tuple(explicit_form) if explicit_form is not None else None,
    )
    required_raw = getattr(meta, "required_fields", None)
    if required_raw is not None:
        required_fields = tuple(required_raw)
    elif form_fields:
        required_fields = (form_fields[0],)
    else:
        required_fields = ("title",)
    ordering = tuple(getattr(meta, "ordering", ("-created_at",)))
    model_lower = model._meta.model_name
    on_load_event = getattr(meta, "on_load_event", None) or f"on_load_{list_var}"
    save_event = getattr(meta, "save_event", None) or f"save_{model_lower}"
    delete_event = getattr(meta, "delete_event", None) or f"delete_{model_lower}"
    load_method = f"_load_{list_var}"
    exclude_from_row = frozenset(getattr(meta, "exclude_from_row", ()) or ())
    if owner_field:
        exclude_from_row = exclude_from_row | frozenset({owner_field})
    return ModelStateConfig(
        serializer_cls=serializer_cls,
        model=model,
        list_var=list_var,
        error_var=error_var,
        form_fields=form_fields,
        owner_field=owner_field,
        ordering=ordering,
        required_fields=required_fields,
        read_only_fields=read_only,
        on_load_event=on_load_event,
        save_event=save_event,
        delete_event=delete_event,
        load_method=load_method,
        exclude_from_row=exclude_from_row,
    )


def maybe_inject_model_state(
    namespace: dict[str, Any],
    bases: tuple[type, ...],
    *,
    qualname: str,
) -> None:
    """Inject generated members into ``namespace`` before Reflex builds the state class."""
    from reflex_django.state.model_state import ModelState

    if ModelState not in bases:
        return
    meta = namespace.get("Meta")
    serializer_cls = getattr(meta, "serializer", None) if meta is not None else None
    if serializer_cls is None:
        return
    config = resolve_model_state_config(serializer_cls, meta)
    inject_model_state_namespace(namespace, config, qualname=qualname)


def inject_model_state_namespace(
    namespace: dict[str, Any],
    config: ModelStateConfig,
    *,
    qualname: str,
) -> None:
    """Add generated vars and event handlers to a class ``namespace`` dict."""
    cfg = config
    annotations = dict(namespace.get("__annotations__", {}))

    if cfg.list_var not in namespace:
        annotations[cfg.list_var] = list[dict[str, Any]]
        namespace[cfg.list_var] = []
    if cfg.error_var not in namespace:
        annotations[cfg.error_var] = str
        namespace[cfg.error_var] = ""
    if "editing_id" not in namespace:
        annotations["editing_id"] = int
        namespace["editing_id"] = -1
    for fname in cfg.form_fields:
        if fname not in namespace:
            annotations[fname] = str
            namespace[fname] = ""
    namespace["__annotations__"] = annotations

    Model = cfg.model
    Serializer = cfg.serializer_cls
    list_var = cfg.list_var
    err_key = cfg.error_var
    owner = cfg.owner_field
    order = cfg.ordering
    form_fields = cfg.form_fields
    required = set(cfg.required_fields)
    exclude_row = cfg.exclude_from_row

    if cfg.load_method not in namespace:

        async def load_impl(self: Any) -> None:
            setattr(self, err_key, "")
            qs = Model.objects.all()
            if owner:
                user = require_login_user()
                qs = qs.filter(**{owner: user})
            qs = qs.order_by(*order)
            rows = await Serializer(qs, many=True, exclude_fields=exclude_row).adata()
            setattr(self, list_var, rows)

        load_impl.__name__ = cfg.load_method
        load_impl.__qualname__ = f"{qualname}.{cfg.load_method}"
        namespace[cfg.load_method] = load_impl

    if cfg.on_load_event not in namespace:

        async def on_load_impl(self: Any) -> None:
            await getattr(self, cfg.load_method)()

        on_load_impl.__name__ = cfg.on_load_event
        on_load_impl.__qualname__ = f"{qualname}.{cfg.on_load_event}"
        namespace[cfg.on_load_event] = rx.event(login_required(on_load_impl))

    if "_clear_form" not in namespace:

        def clear_form_impl(self: Any) -> None:
            for fn in form_fields:
                setattr(self, fn, "")
            self.editing_id = -1

        clear_form_impl.__name__ = "_clear_form"
        clear_form_impl.__qualname__ = f"{qualname}._clear_form"
        namespace["_clear_form"] = clear_form_impl

    for fname in form_fields:
        setter_name = f"set_{fname}"
        if setter_name in namespace:
            continue

        def make_setter(field_name: str = fname) -> Any:
            @rx.event
            def set_field(self: Any, value: str) -> None:
                setattr(self, field_name, value)

            set_field.__name__ = setter_name
            set_field.__qualname__ = f"{qualname}.{setter_name}"
            return set_field

        namespace[setter_name] = make_setter()

    if cfg.save_event not in namespace:

        async def save_impl(self: Any) -> None:
            setattr(self, err_key, "")
            missing = [
                rf
                for rf in required
                if rf in form_fields and not str(getattr(self, rf)).strip()
            ]
            if missing:
                msg = (
                    "Title is required."
                    if missing == ["title"]
                    or (len(missing) == 1 and missing[0] == "title")
                    else f"Required: {', '.join(missing)}"
                )
                setattr(self, err_key, msg)
                return
            user = require_login_user()
            payload = {
                fn: str(getattr(self, fn)).strip() for fn in form_fields
            }
            if getattr(self, "editing_id") >= 0:
                flt: dict[str, Any] = {"pk": getattr(self, "editing_id")}
                if owner:
                    flt[owner] = user
                note = await Model.objects.aget(**flt)
                for key, value in payload.items():
                    setattr(note, key, value)
                await note.asave()
            else:
                create_kwargs = dict(payload)
                if owner:
                    create_kwargs[owner] = user
                await Model.objects.acreate(**create_kwargs)
            getattr(self, "_clear_form")()
            await getattr(self, cfg.load_method)()

        save_impl.__name__ = cfg.save_event
        save_impl.__qualname__ = f"{qualname}.{cfg.save_event}"
        namespace[cfg.save_event] = rx.event(login_required(save_impl))

    if "start_edit" not in namespace:

        async def start_edit_impl(self: Any, item_id: int) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            flt: dict[str, Any] = {"pk": item_id}
            if owner:
                flt[owner] = user
            try:
                note = await Model.objects.aget(**flt)
            except Model.DoesNotExist:
                setattr(self, err_key, f"{Model.__name__} not found.")
                await getattr(self, cfg.load_method)()
                return
            self.editing_id = int(note.pk)
            for fn in form_fields:
                value = getattr(note, fn)
                setattr(self, fn, "" if value is None else str(value))

        start_edit_impl.__name__ = "start_edit"
        start_edit_impl.__qualname__ = f"{qualname}.start_edit"
        namespace["start_edit"] = rx.event(login_required(start_edit_impl))

    if cfg.delete_event not in namespace:

        async def delete_impl(self: Any, item_id: int) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            flt: dict[str, Any] = {"pk": item_id}
            if owner:
                flt[owner] = user
            await Model.objects.filter(**flt).adelete()
            if getattr(self, "editing_id") == item_id:
                getattr(self, "_clear_form")()
            await getattr(self, cfg.load_method)()

        delete_impl.__name__ = cfg.delete_event
        delete_impl.__qualname__ = f"{qualname}.{cfg.delete_event}"
        namespace[cfg.delete_event] = rx.event(login_required(delete_impl))

    if "cancel_edit" not in namespace:

        @rx.event
        def cancel_edit_impl(self: Any) -> None:
            getattr(self, "_clear_form")()

        cancel_edit_impl.__name__ = "cancel_edit"
        cancel_edit_impl.__qualname__ = f"{qualname}.cancel_edit"
        namespace["cancel_edit"] = cancel_edit_impl


def register_state_class(cls: type) -> None:
    """Register ``cls`` on its module (Reflex pickle path)."""
    mod_obj = sys.modules.get(cls.__module__)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)


def populate_model_state_class(cls: type, config: ModelStateConfig | None = None) -> None:
    """Backward-compatible alias for :func:`register_state_class`."""
    del config
    register_state_class(cls)
