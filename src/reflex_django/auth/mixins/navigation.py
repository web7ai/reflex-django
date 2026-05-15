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
) -> None:
    """Add ``redirect_to_login`` for page-level auth guards."""

    @rx.event
    async def redirect_to_login(self: Any) -> Any:
        import reflex_django.auth.routes as auth_routes

        if not self.is_hydrated:
            return type(self).redirect_to_login
        if not self.is_authenticated:
            return rx.redirect(auth_routes.LOGIN_ROUTE)
        return None

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
