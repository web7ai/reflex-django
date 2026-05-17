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
        from reflex_django.context import current_user

        user = current_user()
        return bool(user and getattr(user, "is_authenticated", False))

    ns["is_authenticated"] = is_authenticated

    @rx.event
    async def sync_auth_ui(self: Any) -> None:
        """Refresh auth snapshot and force UI re-render on ``DjangoAuthState``."""
        from reflex_django.auth_state import _mark_auth_ui_dirty
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        _mark_auth_ui_dirty(self)

    ns["sync_auth_ui"] = sync_auth_ui

    @rx.event
    async def redirect_to_login(self: Any) -> Any:
        import reflex_django.auth.routes as auth_routes

        from reflex_django.context import current_user

        if not self.is_hydrated:
            return type(self).redirect_to_login
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        user = current_user()
        if getattr(user, "is_authenticated", False) or self.is_authenticated:
            return None
        return rx.redirect(auth_routes.LOGIN_ROUTE)

    ns["redirect_to_login"] = redirect_to_login


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
