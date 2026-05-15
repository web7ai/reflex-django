"""Declarative Django model list + CRUD as Reflex :class:`reflex.state.State` subclasses."""

from __future__ import annotations

import functools
import inspect
import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import reflex as rx
from django.db import models

from reflex_django.authz import django_login_required, require_login_user
from reflex_django.serialization import serialize_model_row


def _default_row_serializer(
    instance: models.Model,
    *,
    exclude_fields: frozenset[str],
    datetime_format: str = "%Y-%m-%d %H:%M",
    date_format: str = "%Y-%m-%d",
) -> dict[str, Any]:
    """JSON-friendly row dict using :func:`reflex_django.serialization.serialize_model_row`."""
    return serialize_model_row(
        instance,
        exclude_fields=exclude_fields,
        datetime_format=datetime_format,
        date_format=date_format,
    )


@dataclass(frozen=True)
class ModelCRUDConfig:
    """Describe a user-scoped Django model exposed as Reflex state + CRUD events."""

    model: type[models.Model]
    list_var: str
    form_fields: tuple[str, ...]
    error_var: str
    owner_field: str | None = "user"
    ordering: tuple[str, ...] = ("-created_at",)
    required_for_create: tuple[str, ...] = ()
    row_serializer: Callable[..., dict[str, Any]] | None = None
    refresh_method: str = "_refresh_rows"
    on_load_event: str = "on_load_items"
    add_event: str = "add_item"
    delete_event: str = "delete_item"
    exclude_from_row: frozenset[str] = frozenset()
    row_datetime_format: str = "%Y-%m-%d %H:%M"
    row_date_format: str = "%Y-%m-%d"


def crud_mixin(
    cfg: ModelCRUDConfig,
    *,
    base: type[rx.State] = rx.State,
    state_module: str | None = None,
) -> type[rx.State]:
    """Build a concrete :class:`reflex.state.State` subclass with list + form fields + CRUD events.

    Args:
        cfg: Declarative CRUD configuration.
        base: Reflex state base class (e.g. your app ``AppState``).
        state_module: Dotted module name for the generated class ``__module__`` and
            :mod:`sys.modules` registration (Reflex pickle path). Defaults to the
            caller's ``__name__`` when omitted.

    Returns:
        A new state subclass named ``{Model.__name__}CRUDState``.
    """
    frame = inspect.currentframe()
    try:
        if state_module is not None:
            state_mod = state_module
        elif frame is None or frame.f_back is None:
            state_mod = __name__
        else:
            state_mod = str(frame.f_back.f_globals.get("__name__", __name__))
    finally:
        del frame

    Model = cfg.model
    list_var = cfg.list_var
    err_key = cfg.error_var
    owner = cfg.owner_field
    order = cfg.ordering
    form_fields = cfg.form_fields
    required = (
        set(cfg.required_for_create)
        if cfg.required_for_create
        else {cfg.form_fields[0]}
    )
    if cfg.row_serializer is not None:
        row_fn = cfg.row_serializer
    else:
        row_fn = functools.partial(
            _default_row_serializer,
            datetime_format=cfg.row_datetime_format,
            date_format=cfg.row_date_format,
        )
    exclude_row = frozenset(cfg.exclude_from_row)
    if owner:
        exclude_row = exclude_row | frozenset({owner})

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        ann: dict[str, Any] = {
            list_var: list[dict[str, Any]],
            err_key: str,
            "editing_id": int,
        }
        for f in form_fields:
            ann[f"form_{f}"] = str
            ann[f"edit_{f}"] = str
        ns["__annotations__"] = ann
        ns[list_var] = []
        ns[err_key] = ""
        ns["editing_id"] = -1
        for f in form_fields:
            ns[f"form_{f}"] = ""
            ns[f"edit_{f}"] = ""

        async def refresh_impl(self: Any) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            qs = Model.objects.all()
            if owner:
                qs = qs.filter(**{owner: user})
            qs = qs.order_by(*order)
            rows: list[dict[str, Any]] = []
            async for n in qs:
                rows.append(row_fn(n, exclude_fields=exclude_row))
            setattr(self, list_var, rows)

        ns[cfg.refresh_method] = refresh_impl

        async def on_load_impl(self: Any) -> None:
            await getattr(self, cfg.refresh_method)()

        ns[cfg.on_load_event] = rx.event(django_login_required()(on_load_impl))

        for fname in form_fields:

            def make_form_setter(field_name: str = fname) -> Any:
                @rx.event
                def set_form_field(self: Any, v: str) -> None:
                    setattr(self, f"form_{field_name}", v)

                set_form_field.__name__ = f"set_form_{field_name}"
                set_form_field.__qualname__ = (
                    f"{Model.__name__}CRUDState.set_form_{field_name}"
                )
                return set_form_field

            ns[f"set_form_{fname}"] = make_form_setter()

            def make_edit_setter(field_name: str = fname) -> Any:
                @rx.event
                def set_edit_field(self: Any, v: str) -> None:
                    setattr(self, f"edit_{field_name}", v)

                set_edit_field.__name__ = f"set_edit_{field_name}"
                set_edit_field.__qualname__ = (
                    f"{Model.__name__}CRUDState.set_edit_{field_name}"
                )
                return set_edit_field

            ns[f"set_edit_{fname}"] = make_edit_setter()

        async def add_impl(self: Any) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            missing = [
                rf
                for rf in required
                if rf in form_fields and not getattr(self, f"form_{rf}").strip()
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
            create_kwargs: dict[str, Any] = {
                fn: getattr(self, f"form_{fn}").strip() for fn in form_fields
            }
            if owner:
                create_kwargs[owner] = user
            await Model.objects.acreate(**create_kwargs)
            for fn in form_fields:
                setattr(self, f"form_{fn}", "")
            await getattr(self, cfg.refresh_method)()

        ns[cfg.add_event] = rx.event(django_login_required()(add_impl))

        async def start_edit_impl(self: Any, item_id: int) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            flt: dict[str, Any] = {"pk": item_id}
            if owner:
                flt[owner] = user
            try:
                n = await Model.objects.aget(**flt)
            except Model.DoesNotExist:
                setattr(self, err_key, f"{Model.__name__} not found.")
                await getattr(self, cfg.refresh_method)()
                return
            setattr(self, "editing_id", int(n.pk))
            for fn in form_fields:
                setattr(self, f"edit_{fn}", getattr(n, fn))

        ns["start_edit"] = rx.event(django_login_required()(start_edit_impl))

        async def save_edit_impl(self: Any) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            if getattr(self, "editing_id") < 0:
                return
            for rf in required:
                if rf in form_fields and not getattr(self, f"edit_{rf}").strip():
                    setattr(
                        self,
                        err_key,
                        "Title is required." if rf == "title" else f"Required: {rf}",
                    )
                    return
            flt = {"pk": getattr(self, "editing_id")}
            if owner:
                flt[owner] = user
            try:
                n = await Model.objects.aget(**flt)
            except Model.DoesNotExist:
                setattr(self, err_key, f"{Model.__name__} not found.")
                setattr(self, "editing_id", -1)
                await getattr(self, cfg.refresh_method)()
                return
            for fn in form_fields:
                setattr(n, fn, getattr(self, f"edit_{fn}").strip())
            await n.asave()
            setattr(self, "editing_id", -1)
            for fn in form_fields:
                setattr(self, f"edit_{fn}", "")
            await getattr(self, cfg.refresh_method)()

        ns["save_edit"] = rx.event(django_login_required()(save_edit_impl))

        async def cancel_edit_impl(self: Any) -> None:
            setattr(self, "editing_id", -1)
            for fn in form_fields:
                setattr(self, f"edit_{fn}", "")

        ns["cancel_edit"] = rx.event(cancel_edit_impl)

        async def delete_impl(self: Any, item_id: int) -> None:
            setattr(self, err_key, "")
            user = require_login_user()
            flt = {"pk": item_id}
            if owner:
                flt[owner] = user
            deleted, _ = await Model.objects.filter(**flt).adelete()
            if deleted and getattr(self, "editing_id") == item_id:
                setattr(self, "editing_id", -1)
                for fn in form_fields:
                    setattr(self, f"edit_{fn}", "")
            await getattr(self, cfg.refresh_method)()

        ns[cfg.delete_event] = rx.event(django_login_required()(delete_impl))

    cls_name = f"{Model.__name__}CRUDState"
    cls = types.new_class(cls_name, (base,), {}, exec_body)
    # Reflex persistence pickles state by module path; dynamic types must live on
    # the module dict or picklers cannot resolve the class by name.
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = ["ModelCRUDConfig", "crud_mixin", "_default_row_serializer"]
