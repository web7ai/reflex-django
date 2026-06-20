"""Navigation helpers for auth state (login redirect)."""

from __future__ import annotations

import inspect
import sys
import types
from typing import Any

import reflex as rx


def populate_navigation_state(
    ns: dict[str, Any],
    *,
    cls_name: str,
    annotations: dict[str, type] | None = None,
) -> None:
    """Add ``redirect_to_login``, ``sync_auth_ui``, and live auth computed var."""
    del annotations

    @rx.var
    def is_authenticated(self) -> bool:
        """Live session check for UI (replaces inherited snapshot field on ``DjangoAuthState``)."""
        from reflex_django.bridge.context import current_user

        user = current_user()
        return bool(user and getattr(user, "is_authenticated", False))

    ns["is_authenticated"] = is_authenticated

    @rx.event
    async def sync_auth_ui(self: Any) -> None:
        """Refresh auth snapshot and force UI re-render on ``DjangoAuthState``."""
        from reflex_django.states.auth import _mark_auth_ui_dirty
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        _mark_auth_ui_dirty(self)

    ns["sync_auth_ui"] = sync_auth_ui

    @rx.event
    async def redirect_to_login(self: Any) -> Any:
        import reflex_django.auth.routes as auth_routes

        from reflex_django.bridge.context import current_user

        if not self.is_hydrated:
            return type(self).redirect_to_login
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        user = current_user()
        if getattr(user, "is_authenticated", False) or self.is_authenticated:
            return None
        return rx.redirect(auth_routes.LOGIN_ROUTE)

    ns["redirect_to_login"] = redirect_to_login

    async def _enforce_access(
        self: Any,
        *,
        check_name: str,
        value: str,
        redirect_to: str,
    ) -> Any:
        """Authoritative server-side page guard.

        Runs on mount for every protected page so an authenticated user who
        lacks the required permission/role is redirected instead of seeing the
        page shell (the UI ``rx.cond`` alone is not a security boundary).
        """
        import reflex_django.auth.routes as auth_routes
        from reflex_django.bridge.context import current_user
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        user = current_user()
        login_route = auth_routes.LOGIN_ROUTE
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(login_route)

        allowed = True
        if check_name == "perm":
            from reflex_django.auth.shortcuts import auser_has_perm

            allowed = await auser_has_perm(user, value)
        elif check_name == "group":
            from reflex_django.auth.shortcuts import auser_in_group

            allowed = await auser_in_group(user, value)
        elif check_name == "staff":
            allowed = bool(getattr(user, "is_staff", False))
        elif check_name == "superuser":
            allowed = bool(getattr(user, "is_superuser", False))

        if allowed:
            return None
        return rx.redirect(redirect_to or login_route)

    @rx.event
    async def require_permission(
        self: Any,
        perm: str,
        redirect_to: str = "",
    ) -> Any:
        """Redirect on mount unless the Django user holds ``perm``."""
        if not self.is_hydrated:
            return type(self).require_permission(perm, redirect_to)
        return await _enforce_access(
            self, check_name="perm", value=perm, redirect_to=redirect_to
        )

    ns["require_permission"] = require_permission

    @rx.event
    async def require_group(
        self: Any,
        group: str,
        redirect_to: str = "",
    ) -> Any:
        """Redirect on mount unless the Django user is in ``group``."""
        if not self.is_hydrated:
            return type(self).require_group(group, redirect_to)
        return await _enforce_access(
            self, check_name="group", value=group, redirect_to=redirect_to
        )

    ns["require_group"] = require_group

    @rx.event
    async def require_staff(self: Any, redirect_to: str = "") -> Any:
        """Redirect on mount unless the Django user is staff."""
        if not self.is_hydrated:
            return type(self).require_staff(redirect_to)
        return await _enforce_access(
            self, check_name="staff", value="", redirect_to=redirect_to
        )

    ns["require_staff"] = require_staff

    @rx.event
    async def require_superuser(self: Any, redirect_to: str = "") -> Any:
        """Redirect on mount unless the Django user is a superuser."""
        if not self.is_hydrated:
            return type(self).require_superuser(redirect_to)
        return await _enforce_access(
            self, check_name="superuser", value="", redirect_to=redirect_to
        )

    ns["require_superuser"] = require_superuser


def navigation_mixin(
    *,
    base: type[rx.State],
    state_module: str | None = None,
    state_class_name: str = "DjangoAuthState",
) -> type[rx.State]:
    """Add ``redirect_to_login`` for page-level auth guards."""
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

    cls_name = state_class_name

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        populate_navigation_state(ns, cls_name=cls_name)

    cls = types.new_class(cls_name, (base,), {}, exec_body)
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = ["navigation_mixin", "populate_navigation_state"]
