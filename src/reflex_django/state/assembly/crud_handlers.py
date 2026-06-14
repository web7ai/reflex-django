"""CRUD handler assembly for model state classes."""

from __future__ import annotations

from typing import Any

import reflex as rx

from reflex_django.state.constants import (
    ACTION_CANCEL_EDIT,
    ACTION_DELETE,
    ACTION_SAVE,
    ACTION_START_EDIT,
)
from reflex_django.state.mixins.queryset import QuerySetMixin
from reflex_django.state.mixins.scoping import UserScopedMixin
from reflex_django.state.options import ModelStateOptions

from reflex_django.state.assembly.meta import bind_event


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
