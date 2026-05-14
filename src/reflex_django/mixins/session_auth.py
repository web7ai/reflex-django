"""Declarative Django session login/logout as Reflex :class:`reflex.state.State` subclasses."""

from __future__ import annotations

import inspect
import sys
import types
from dataclasses import dataclass
from typing import Any

import reflex as rx
from django.contrib.auth import aauthenticate, alogin, alogout

from reflex_django.auth_state import DjangoUserState
from reflex_django.context import current_request


@dataclass(frozen=True)
class SessionAuthConfig:
    """Describe login form fields, events, and redirects for session auth."""

    username_var: str = "login_username"
    password_var: str = "login_password"
    error_var: str = "login_error"
    on_load_event: str = "on_load_login"
    submit_event: str = "submit_login"
    logout_event: str = "logout"
    post_login_redirect: str = "/"
    post_logout_redirect: str = "/login"
    redirect_when_authenticated: str | None = None
    session_unavailable_message: str = "Session unavailable. Reload the page."
    invalid_credentials_message: str = "Invalid username or password."
    state_class_name: str = "SessionAuthState"


def session_auth_mixin(
    cfg: SessionAuthConfig,
    *,
    base: type[rx.State] = DjangoUserState,
    state_module: str | None = None,
) -> type[rx.State]:
    """Build a concrete :class:`reflex.state.State` subclass with login/logout events.

    Uses Django async session auth (:func:`~django.contrib.auth.aauthenticate`,
    :func:`~django.contrib.auth.alogin`, :func:`~django.contrib.auth.alogout`)
    and :func:`reflex_django.context.current_request` inside Reflex event handlers.

    Args:
        cfg: Declarative session auth configuration.
        base: Reflex state base class; default includes :class:`DjangoUserState`
            so :meth:`~DjangoUserState.refresh_django_user_fields` is available.
        state_module: Dotted module name for the generated class ``__module__`` and
            :mod:`sys.modules` registration (Reflex pickle path). Defaults to the
            caller's ``__name__`` when omitted.

    Returns:
        A new state subclass named per ``cfg.state_class_name`` (default ``SessionAuthState``).
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

    u_var = cfg.username_var
    p_var = cfg.password_var
    e_var = cfg.error_var
    post_in = cfg.post_login_redirect
    post_out = cfg.post_logout_redirect
    when_auth = cfg.redirect_when_authenticated
    msg_no_session = cfg.session_unavailable_message
    msg_bad = cfg.invalid_credentials_message

    cls_name = cfg.state_class_name

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        ns["__annotations__"] = {
            u_var: str,
            p_var: str,
            e_var: str,
        }
        ns[u_var] = ""
        ns[p_var] = ""
        ns[e_var] = ""

        async def on_load_impl(self: Any) -> Any:
            await self.refresh_django_user_fields()
            if when_auth is not None and self.is_authenticated:
                return rx.redirect(when_auth)
            return None

        ns[cfg.on_load_event] = rx.event(on_load_impl)

        def make_user_setter() -> Any:
            @rx.event
            def set_username(self: Any, v: str) -> None:
                setattr(self, u_var, v)

            set_username.__name__ = f"set_{u_var}"
            set_username.__qualname__ = f"{cls_name}.set_{u_var}"
            return set_username

        def make_pass_setter() -> Any:
            @rx.event
            def set_password(self: Any, v: str) -> None:
                setattr(self, p_var, v)

            set_password.__name__ = f"set_{p_var}"
            set_password.__qualname__ = f"{cls_name}.set_{p_var}"
            return set_password

        ns[f"set_{u_var}"] = make_user_setter()
        ns[f"set_{p_var}"] = make_pass_setter()

        async def submit_impl(self: Any) -> Any:
            setattr(self, e_var, "")
            request = current_request()
            if request is None:
                setattr(self, e_var, msg_no_session)
                return
            user = await aauthenticate(
                request,
                username=getattr(self, u_var).strip(),
                password=getattr(self, p_var),
            )
            if user is None:
                setattr(self, e_var, msg_bad)
                setattr(self, p_var, "")
                return
            await alogin(request, user)
            setattr(self, p_var, "")
            await self.refresh_django_user_fields()
            return rx.redirect(post_in)

        ns[cfg.submit_event] = rx.event(submit_impl)

        async def logout_impl(self: Any) -> Any:
            request = current_request()
            if request is not None:
                await alogout(request)
            await self.refresh_django_user_fields()
            return rx.redirect(post_out)

        ns[cfg.logout_event] = rx.event(logout_impl)

    cls = types.new_class(cls_name, (base,), {}, exec_body)
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = ["SessionAuthConfig", "session_auth_mixin"]
