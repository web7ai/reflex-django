"""Assemble model state classes: vars, handlers, and module registration."""

from __future__ import annotations

import sys
from typing import Any

import reflex as rx

from reflex_django.state.constants import (
    ACTION_CANCEL_EDIT,
    ACTION_DELETE,
    ACTION_LOAD_LIST,
    ACTION_SAVE,
    ACTION_START_EDIT,
)
from reflex_django.state.options import ModelStateOptions, resolve_options
from reflex_django.state.mixins.queryset import QuerySetMixin
from reflex_django.state.mixins.scoping import UserScopedMixin
from reflex_django.state.views.crud import ModelCRUDView
from reflex_django.state.views.list import ModelListView

_MODEL_STATE_BASES = (ModelCRUDView, ModelListView)


def _needs_assembly(bases: tuple[type, ...]) -> bool:
    for b in bases:
        if isinstance(b, type) and issubclass(b, _MODEL_STATE_BASES):
            return True
    return False


def _resolve_serializer(
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
    return None


def bind_event(
    handler: Any,
    *,
    login_required: bool,
) -> Any:
    if login_required:
        from reflex_django.auth.decorators import login_required

        return rx.event(login_required(handler))
    return rx.event(handler)


def assemble_model_state_namespace(
    namespace: dict[str, Any],
    bases: tuple[type, ...],
    *,
    qualname: str,
    state_cls_name: str,
) -> ModelStateOptions | None:
    """Inject vars and default handlers before Reflex builds the state class."""
    if not _needs_assembly(bases):
        return None

    serializer_cls = _resolve_serializer(namespace, bases)
    if serializer_cls is None:
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

    options = resolve_options(serializer_cls, meta, holder)  # type: ignore[arg-type]
    namespace["_model_state_options"] = options

    annotations = dict(namespace.get("__annotations__", {}))

    if options.list_var not in namespace:
        annotations[options.list_var] = list[dict[str, Any]]
        namespace[options.list_var] = []
    if options.error_var not in namespace:
        annotations[options.error_var] = str
        namespace[options.error_var] = ""
    if options.field_errors_var and options.field_errors_var not in namespace:
        annotations[options.field_errors_var] = dict[str, str]
        namespace[options.field_errors_var] = {}
    if options.editing_var not in namespace:
        annotations[options.editing_var] = int
        namespace[options.editing_var] = -1

    is_crud = any(
        b is ModelCRUDView or (isinstance(b, type) and issubclass(b, ModelCRUDView))
        for b in bases
    )
    if is_crud and options.form_reset_var and options.form_reset_var not in namespace:
        annotations[options.form_reset_var] = int
        namespace[options.form_reset_var] = 0

    _assemble_list_features(namespace, options, qualname=qualname)

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

    if UserScopedMixin in bases:
        _inject_user_scoped(namespace, qualname=qualname)

    return options


def _assemble_list_features(
    namespace: dict[str, Any],
    options: ModelStateOptions,
    *,
    qualname: str,
) -> None:
    """Inject pagination, search, and ordering vars/events when enabled in Meta."""
    annotations = dict(namespace.get("__annotations__", {}))
    lr_load = ACTION_LOAD_LIST in options.login_required_actions

    if options.paginate_by is not None:
        if options.page_var not in namespace:
            annotations[options.page_var] = int
            namespace[options.page_var] = 1
        if options.page_size_var not in namespace:
            annotations[options.page_size_var] = int
            namespace[options.page_size_var] = options.paginate_by
        if options.total_count_var not in namespace:
            annotations[options.total_count_var] = int
            namespace[options.total_count_var] = 0
        if options.page_count_var not in namespace:
            annotations[options.page_count_var] = int
            namespace[options.page_count_var] = 0

    if options.search_fields and options.search_var not in namespace:
        annotations[options.search_var] = str
        namespace[options.search_var] = ""

    if options.allow_dynamic_ordering and options.ordering_var not in namespace:
        annotations[options.ordering_var] = str
        default_order = options.ordering[0] if options.ordering else ""
        namespace[options.ordering_var] = default_order

    namespace["__annotations__"] = annotations

    async def reload_list(self: Any) -> None:
        await getattr(self, options.load_method)()

    if options.paginate_by is not None:

        if "next_page" not in namespace:

            async def next_page_impl(self: Any) -> None:
                opts = self.get_options()
                page = int(getattr(self, opts.page_var))
                page_count = int(getattr(self, opts.page_count_var))
                if page < page_count:
                    setattr(self, opts.page_var, page + 1)
                    self.on_page_change(page + 1)
                    await reload_list(self)

            next_page_impl.__name__ = "next_page"
            next_page_impl.__qualname__ = f"{qualname}.next_page"
            namespace["next_page"] = bind_event(next_page_impl, login_required=lr_load)

        if "prev_page" not in namespace:

            async def prev_page_impl(self: Any) -> None:
                opts = self.get_options()
                page = int(getattr(self, opts.page_var))
                if page > 1:
                    setattr(self, opts.page_var, page - 1)
                    self.on_page_change(page - 1)
                    await reload_list(self)

            prev_page_impl.__name__ = "prev_page"
            prev_page_impl.__qualname__ = f"{qualname}.prev_page"
            namespace["prev_page"] = bind_event(prev_page_impl, login_required=lr_load)

        if "go_to_page" not in namespace:

            async def go_to_page_impl(self: Any, page: int) -> None:
                opts = self.get_options()
                page_count = max(1, int(getattr(self, opts.page_count_var)))
                clamped = max(1, min(int(page), page_count))
                setattr(self, opts.page_var, clamped)
                self.on_page_change(clamped)
                await reload_list(self)

            go_to_page_impl.__name__ = "go_to_page"
            go_to_page_impl.__qualname__ = f"{qualname}.go_to_page"
            namespace["go_to_page"] = bind_event(go_to_page_impl, login_required=lr_load)

        if "set_page_size" not in namespace:

            async def set_page_size_impl(self: Any, size: int) -> None:
                opts = self.get_options()
                clamped = min(max(1, int(size)), opts.max_page_size)
                setattr(self, opts.page_size_var, clamped)
                setattr(self, opts.page_var, 1)
                self.on_page_change(1)
                await reload_list(self)

            set_page_size_impl.__name__ = "set_page_size"
            set_page_size_impl.__qualname__ = f"{qualname}.set_page_size"
            namespace["set_page_size"] = bind_event(set_page_size_impl, login_required=lr_load)

    if options.search_fields:
        set_search_name = f"set_{options.search_var}"

        if set_search_name not in namespace:

            async def set_search_impl(self: Any, value: str) -> None:
                setattr(self, options.search_var, str(value))
                self.reset_page()
                await reload_list(self)

            set_search_impl.__name__ = set_search_name
            set_search_impl.__qualname__ = f"{qualname}.{set_search_name}"
            namespace[set_search_name] = bind_event(set_search_impl, login_required=lr_load)

        clear_search_name = f"clear_{options.search_var}"

        if clear_search_name not in namespace:

            async def clear_search_impl(self: Any) -> None:
                setattr(self, options.search_var, "")
                self.reset_page()
                await reload_list(self)

            clear_search_impl.__name__ = clear_search_name
            clear_search_impl.__qualname__ = f"{qualname}.{clear_search_name}"
            namespace[clear_search_name] = bind_event(clear_search_impl, login_required=lr_load)

    if options.allow_dynamic_ordering:
        set_ordering_name = f"set_{options.ordering_var}"

        if set_ordering_name not in namespace:

            async def set_ordering_impl(self: Any, value: str) -> None:
                setattr(self, options.ordering_var, str(value).strip())
                self.reset_page()
                await reload_list(self)

            set_ordering_impl.__name__ = set_ordering_name
            set_ordering_impl.__qualname__ = f"{qualname}.{set_ordering_name}"
            namespace[set_ordering_name] = bind_event(set_ordering_impl, login_required=lr_load)


def _inject_user_scoped(namespace: dict[str, Any], *, qualname: str) -> None:
    """Apply :class:`UserScopedMixin` hooks (Reflex MRO cannot prioritize plain mixins)."""
    scope_field = namespace.get("scope_field", UserScopedMixin.scope_field)

    if "get_queryset" not in namespace:

        def get_queryset(self: Any) -> Any:
            user = self.get_user()
            value = user if scope_field == "user" else user.pk
            return QuerySetMixin.get_queryset(self).filter(**{scope_field: value})

        get_queryset.__name__ = "get_queryset"
        get_queryset.__qualname__ = f"{qualname}.get_queryset"
        namespace["get_queryset"] = get_queryset

    if "get_object_lookup" not in namespace:

        def get_object_lookup(self: Any, pk: int) -> dict[str, Any]:
            from reflex_django.state.mixins.object import ObjectMixin

            lookup = ObjectMixin.get_object_lookup(self, pk)
            user = self.get_user()
            lookup[scope_field] = user if scope_field == "user" else user.pk
            return lookup

        get_object_lookup.__name__ = "get_object_lookup"
        get_object_lookup.__qualname__ = f"{qualname}.get_object_lookup"
        namespace["get_object_lookup"] = get_object_lookup

    if "get_create_kwargs" not in namespace:

        def get_create_kwargs(self: Any, state_data: dict[str, Any]) -> dict[str, Any]:
            from reflex_django.state.mixins.create import CreateMixin

            kwargs = CreateMixin.get_create_kwargs(self, state_data)
            user = self.get_user()
            kwargs[scope_field] = user if scope_field == "user" else user.pk
            return kwargs

        get_create_kwargs.__name__ = "get_create_kwargs"
        get_create_kwargs.__qualname__ = f"{qualname}.get_create_kwargs"
        namespace["get_create_kwargs"] = get_create_kwargs


def _assemble_crud_handlers(
    namespace: dict[str, Any],
    options: ModelStateOptions,
    *,
    qualname: str,
) -> None:
    if "reset_state_fields" not in namespace:
        from reflex_django.state.mixins.state_fields import StateFieldsMixin

        def reset_impl(self: Any) -> None:
            StateFieldsMixin.reset_state_fields(self)

        reset_impl.__name__ = "reset_state_fields"
        reset_impl.__qualname__ = f"{qualname}.reset_state_fields"
        namespace["reset_state_fields"] = reset_impl

    if "_reset_state_fields" not in namespace:

        def reset_legacy_impl(self: Any) -> None:
            self.reset_state_fields()

        reset_legacy_impl.__name__ = "_reset_state_fields"
        reset_legacy_impl.__qualname__ = f"{qualname}._reset_state_fields"
        namespace["_reset_state_fields"] = reset_legacy_impl

    for sf in options.state_fields:
        setter_name = f"set_{sf.name}"
        if setter_name in namespace:
            continue

        def make_setter(field_name: str = sf.name) -> Any:
            @rx.event
            def set_field(self: Any, value: Any) -> None:
                opts = self.get_options()
                for field in opts.state_fields:
                    if field.name == field_name:
                        setattr(self, field_name, field.to_var(value))
                        break
                on_change = getattr(self, "on_state_field_change", None)
                if on_change is not None:
                    on_change(field_name, value)

            set_field.__name__ = setter_name
            set_field.__qualname__ = f"{qualname}.{setter_name}"
            return set_field

        namespace[setter_name] = make_setter()

    if options.save_event not in namespace:

        async def save_impl(self: Any) -> None:
            await self.dispatch(ACTION_SAVE)

        save_impl.__name__ = options.save_event
        save_impl.__qualname__ = f"{qualname}.{options.save_event}"
        lr = ACTION_SAVE in options.login_required_actions
        namespace[options.save_event] = bind_event(save_impl, login_required=lr)

    if options.use_form_submit:
        form_event = f"{options.save_event}_form"
        if form_event not in namespace:

            async def save_form_impl(self: Any, form_data: dict[str, Any]) -> None:
                self.apply_form_data(form_data)
                await self.dispatch(ACTION_SAVE)

            save_form_impl.__name__ = form_event
            save_form_impl.__qualname__ = f"{qualname}.{form_event}"
            lr = ACTION_SAVE in options.login_required_actions
            namespace[form_event] = bind_event(save_form_impl, login_required=lr)

    if options.delete_event not in namespace:

        async def delete_impl(self: Any, item_id: int) -> None:
            await self.dispatch(ACTION_DELETE, pk=item_id)

        delete_impl.__name__ = options.delete_event
        delete_impl.__qualname__ = f"{qualname}.{options.delete_event}"
        lr = ACTION_DELETE in options.login_required_actions
        namespace[options.delete_event] = bind_event(delete_impl, login_required=lr)

    if "start_edit" not in namespace:

        async def start_edit_impl(self: Any, item_id: int) -> None:
            await self.dispatch(ACTION_START_EDIT, pk=item_id)

        start_edit_impl.__name__ = "start_edit"
        start_edit_impl.__qualname__ = f"{qualname}.start_edit"
        lr = ACTION_START_EDIT in options.login_required_actions
        namespace["start_edit"] = bind_event(start_edit_impl, login_required=lr)

    if options.cancel_event not in namespace:

        @rx.event
        async def cancel_impl(self: Any) -> None:
            await self.dispatch(ACTION_CANCEL_EDIT)

        cancel_impl.__name__ = options.cancel_event
        cancel_impl.__qualname__ = f"{qualname}.{options.cancel_event}"
        namespace[options.cancel_event] = cancel_impl


def register_state_class(cls: type) -> None:
    """Register ``cls`` on its module (Reflex pickle path)."""
    mod_obj = sys.modules.get(cls.__module__)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)


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


__all__ = [
    "assemble_model_state_namespace",
    "bind_event",
    "maybe_assemble_model_state",
    "register_state_class",
]
