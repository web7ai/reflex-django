"""Central dispatch pipeline for model state actions."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from reflex_django.state.base import ActionContext, BaseModelState
from reflex_django.state.constants import (
    ACTION_CANCEL_EDIT,
    ACTION_DELETE,
    ACTION_LOAD_LIST,
    ACTION_SAVE,
    ACTION_START_EDIT,
)
from reflex_django.state.mixins.create import CreateMixin
from reflex_django.state.mixins.delete import DeleteMixin
from reflex_django.state.mixins.permission import PermissionMixin


class DispatchMixin(DeleteMixin, CreateMixin, PermissionMixin):
    """Route actions through setup → permissions → handler → teardown."""

    def get_action_handler(
        self,
        action: str,
    ) -> Callable[[ActionContext], Awaitable[Any]]:
        handlers: dict[str, Callable[[ActionContext], Awaitable[Any]]] = {
            ACTION_LOAD_LIST: self._handle_load_list,
            ACTION_SAVE: self._handle_save,
            ACTION_DELETE: self._handle_delete,
            ACTION_START_EDIT: self.handle_start_edit,
            ACTION_CANCEL_EDIT: self.handle_cancel_edit,
        }
        handler = handlers.get(action)
        if handler is None:
            msg = f"Unknown action: {action!r}"
            raise ValueError(msg)
        return handler

    async def dispatch(self, action: str, **kwargs: Any) -> Any:
        await self.bind_request_context()
        ctx = self.build_context(action, **kwargs)
        self.setup(action)
        try:
            self.check_permissions(ctx)
            handler = self.get_action_handler(action)
            return await handler(ctx)
        except Exception as exc:
            self.handle_exception(ctx, exc)
            return None
        finally:
            self.teardown(action)

    async def _handle_load_list(self, ctx: ActionContext) -> None:
        await self.load_list(ctx)

    async def _handle_save(self, ctx: ActionContext) -> None:
        opts = ctx.options
        state_data, errors = await self.validate_and_clean(ctx)
        if errors:
            self.on_state_invalid(ctx, errors)
            return
        assert state_data is not None
        state_data = await self.on_state_valid(ctx, state_data)
        editing_var = opts.editing_var
        editing_id = getattr(self, editing_var, -1)
        if editing_id is not None and int(editing_id) >= 0:
            instance = await ctx.backend.retrieve(ctx, int(editing_id))
            if not self.has_object_permission(ctx, instance):
                self.on_state_invalid(ctx, {"__all__": "Permission denied."})
                return
            instance = await ctx.backend.update(ctx, instance, state_data)
        else:
            instance = await ctx.backend.create(ctx, state_data)
        await self.on_save_success(ctx, instance)
        if opts.reset_after_save:
            self.reset_state_fields()
        await self.refresh_list(ctx)

    async def _handle_delete(self, ctx: ActionContext) -> None:
        await self.handle_delete(ctx)


__all__ = ["DispatchMixin"]
