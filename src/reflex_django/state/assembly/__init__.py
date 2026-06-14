"""Assemble model state classes: vars, handlers, and module registration."""

from __future__ import annotations

import sys
from typing import Any

import reflex as rx
from django.core.exceptions import ImproperlyConfigured

from reflex_django.state.constants import ACTION_LOAD_LIST
from reflex_django.state.mixins.scoping import UserScopedMixin
from reflex_django.state.options import ModelStateOptions, resolve_options
from reflex_django.state.views.crud import ModelCRUDView

from reflex_django.state.assembly.crud_handlers import (
    _assemble_crud_handlers,
    _inject_user_scoped,
)
from reflex_django.state.assembly.list_handlers import _assemble_list_features
from reflex_django.state.assembly.meta import (
    bind_event,
    extract_model_and_fields,
    inject_var_default,
    needs_assembly,
    resolve_serializer,
    uses_model_state_base,
)
from reflex_django.state.assembly.orm_api_handlers import _assemble_orm_api_handlers

__all__ = [
    "assemble_model_state_namespace",
    "bind_event",
    "inject_simple_var_setters",
    "maybe_assemble_model_state",
    "maybe_inject_var_setters",
    "register_state_class",
]


def assemble_model_state_namespace(
    namespace: dict[str, Any],
    bases: tuple[Any, ...],
    *,
    qualname: str,
    state_cls_name: str,
) -> ModelStateOptions | None:
    """Inject vars and default handlers before Reflex builds the state class."""
    if not needs_assembly(bases):
        return None

    model, _, _ = extract_model_and_fields(namespace, bases)
    if model is not None and "model" not in namespace:
        namespace["model"] = model

    serializer_cls = resolve_serializer(namespace, bases)
    if serializer_cls is None:
        if uses_model_state_base(bases):
            model, fields, _ = extract_model_and_fields(namespace, bases)
            msg = (
                f"{state_cls_name} must set `model` and `fields` on a "
                "`ModelState` subclass, or provide `serializer_class` / `Meta.serializer`."
            )
            if model is None:
                msg = (
                    f"{state_cls_name}: set `model = YourModel` on the class body "
                    "(e.g. `model = Note`), or use optional `ModelState[Note]`."
                )
            elif not fields:
                msg = f"{state_cls_name}: `fields` is required when `model = {model.__name__}`."
            raise ImproperlyConfigured(msg)
        return None

    meta = namespace.get("Meta")

    class _OptsHolder:
        pass

    holder = _OptsHolder()
    for key, val in namespace.items():
        if key != "Meta":
            setattr(holder, key, val)
    if meta is not None:
        holder.Meta = meta

    options = resolve_options(
        serializer_cls,
        meta,
        holder,  # type: ignore[arg-type]
        use_generic_var_names=uses_model_state_base(bases),
    )
    namespace["_model_state_options"] = options

    annotations = dict(namespace.get("__annotations__", {}))

    inject_var_default(
        namespace, annotations, bases, options.list_var, list[dict[str, Any]], []
    )
    inject_var_default(namespace, annotations, bases, options.error_var, str, "")
    if options.field_errors_var:
        inject_var_default(
            namespace,
            annotations,
            bases,
            options.field_errors_var,
            dict[str, str],
            {},
        )
    inject_var_default(namespace, annotations, bases, options.editing_var, int, -1)

    is_crud = any(
        b is ModelCRUDView or (isinstance(b, type) and issubclass(b, ModelCRUDView))
        for b in bases
    )
    if is_crud and options.form_reset_var:
        inject_var_default(
            namespace, annotations, bases, options.form_reset_var, int, 0
        )

    _assemble_list_features(namespace, options, bases=bases, qualname=qualname)

    for sf in options.state_fields:
        if sf.name not in namespace:
            annotations[sf.name] = sf.var_type
            namespace[sf.name] = sf.to_var(None)

    namespace["__annotations__"] = annotations

    if options.load_method not in namespace:
        if is_crud:

            async def load_impl(self: Any) -> None:
                await self.dispatch(ACTION_LOAD_LIST)

        else:

            async def load_impl(self: Any) -> None:
                await self.bind_request_context()
                ctx = self.build_context(ACTION_LOAD_LIST)
                try:
                    self.check_permissions(ctx)
                    await self.load_list(ctx)
                except Exception as exc:
                    self.handle_exception(ctx, exc)
                finally:
                    self.teardown(ACTION_LOAD_LIST)

        load_impl.__name__ = options.load_method
        load_impl.__qualname__ = f"{qualname}.{options.load_method}"
        namespace[options.load_method] = load_impl

    if options.on_load_event not in namespace:

        async def on_load_impl(self: Any) -> None:
            await getattr(self, options.load_method)()

        on_load_impl.__name__ = options.on_load_event
        on_load_impl.__qualname__ = f"{qualname}.{options.on_load_event}"
        lr = options.on_load_event in options.login_required_actions
        namespace[options.on_load_event] = bind_event(on_load_impl, login_required=lr)

    if is_crud:
        _assemble_crud_handlers(namespace, options, qualname=qualname)
        if options.use_canonical_api:
            _assemble_orm_api_handlers(namespace, options, qualname=qualname)

    if UserScopedMixin in bases:
        _inject_user_scoped(namespace, qualname=qualname)

    return options


def register_state_class(cls: type) -> None:
    """Register ``cls`` on its module (Reflex pickle path)."""
    mod_obj = sys.modules.get(cls.__module__)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)


_SIMPLE_VAR_TYPES = (str, int, bool, float)
_SIMPLE_VAR_TYPE_NAMES = frozenset({"str", "int", "bool", "float"})


def _is_simple_var_type(annotation: Any) -> bool:
    if annotation in _SIMPLE_VAR_TYPES:
        return True
    if isinstance(annotation, str):
        return annotation in _SIMPLE_VAR_TYPE_NAMES
    return False


def inject_simple_var_setters(
    namespace: dict[str, Any],
    *,
    qualname: str,
) -> None:
    """Add ``set_{field}`` handlers for manual :class:`~reflex_django.states.AppState` form vars.

    Reflex 0.9+ disables automatic setters; :class:`~reflex_django.state.ModelCRUDView`
    still injects them during assembly. Plain states (e.g. profile forms) need this pass.
    """
    annotations = namespace.get("__annotations__", {})
    for name, type_ann in annotations.items():
        if name.startswith("_") or not _is_simple_var_type(type_ann):
            continue
        if name not in namespace:
            continue
        setter_name = f"set_{name}"
        if setter_name in namespace:
            continue

        def make_setter(field_name: str = name, field_type: Any = type_ann) -> Any:
            @rx.event
            def set_field(self: Any, value: Any) -> None:
                if field_type is bool:
                    setattr(self, field_name, bool(value))
                elif field_type is int:
                    setattr(self, field_name, int(value))
                elif field_type is float:
                    setattr(self, field_name, float(value))
                else:
                    setattr(self, field_name, "" if value is None else str(value))

            set_field.__name__ = setter_name
            set_field.__qualname__ = f"{qualname}.{setter_name}"
            return set_field

        namespace[setter_name] = make_setter()


def maybe_inject_var_setters(
    namespace: dict[str, Any],
    bases: tuple[type, ...],
    *,
    qualname: str,
) -> None:
    """Inject form setters for non-CRUD states when the class body declares backend vars."""
    if needs_assembly(bases) or uses_model_state_base(bases):
        return
    inject_simple_var_setters(namespace, qualname=qualname)


def maybe_assemble_model_state(
    namespace: dict[str, Any],
    bases: tuple[type, ...],
    *,
    qualname: str,
    state_cls_name: str,
) -> None:
    assemble_model_state_namespace(
        namespace,
        bases,
        qualname=qualname,
        state_cls_name=state_cls_name,
    )
