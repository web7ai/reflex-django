"""Permission checks for model state actions."""

from __future__ import annotations

from typing import Any, Protocol

from reflex_django.state.base import ActionContext, BaseModelState


class Permission(Protocol):
    def has_permission(self, state: Any, ctx: ActionContext) -> bool: ...

    def has_object_permission(
        self,
        state: Any,
        ctx: ActionContext,
        obj: Any,
    ) -> bool: ...


class AllowAny:
    def has_permission(self, state: Any, ctx: ActionContext) -> bool:
        return True

    def has_object_permission(self, state: Any, ctx: ActionContext, obj: Any) -> bool:
        return True


class IsAuthenticated:
    def has_permission(self, state: Any, ctx: ActionContext) -> bool:
        return ctx.user is not None

    def has_object_permission(self, state: Any, ctx: ActionContext, obj: Any) -> bool:
        return ctx.user is not None


class PermissionMixin(BaseModelState):
    """Run ``permission_classes`` before actions."""

    def check_permissions(self, ctx: ActionContext) -> None:
        for perm_cls in self.get_options().permission_classes:
            perm = perm_cls()
            if not perm.has_permission(self, ctx):
                msg = "Permission denied."
                raise PermissionError(msg)

    def has_object_permission(self, ctx: ActionContext, obj: Any) -> bool:
        for perm_cls in self.get_options().permission_classes:
            perm = perm_cls()
            if not perm.has_object_permission(self, ctx, obj):
                return False
        return True


__all__ = ["AllowAny", "IsAuthenticated", "Permission", "PermissionMixin"]
