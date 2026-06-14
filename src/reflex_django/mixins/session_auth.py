"""Declarative Django session login/logout as Reflex :class:`reflex.state.State` subclasses."""

from __future__ import annotations

import inspect
import json
import sys
import types
from dataclasses import dataclass
from typing import Any

import reflex as rx

from reflex_django.auth.login_fields import DEFAULT_LOGIN_FIELDS
from reflex_django.states.auth import DjangoUserState
from reflex_django.bridge.context import current_request
from reflex_django.state.auth_bridge import AuthBridgeMixin, session_async_save

_NAV_DELAY_MS = 200


def _defer_nav_js(path: str) -> str:
    href = json.dumps(path)
    return (
        f"setTimeout(function(){{ window.location.replace({href}); }}, {_NAV_DELAY_MS});"
    )


def _sync_session_cookie_then_nav(
    request: Any,
    path: str,
    *,
    clear_cookie: bool = False,
) -> Any:
    """Mirror Django session to ``document.cookie``, then hard-navigate.

    Reflex events do not run ``SessionMiddleware``, so the browser often never
    receives ``Set-Cookie`` after ``alogin`` / ``alogout``. Without syncing the
    session key here, the next document load can still send a stale ``sessionid``.
    See :mod:`reflex_django.bridge.session_js` and ``SESSION_COOKIE_HTTPONLY``.

    Navigation is deferred briefly so the cookie write is applied before the
    next load.
    """
    from reflex_django.bridge.session_js import (
        browser_auth_logout_clear_js,
        browser_session_storage_clear_js,
        session_cookie_clear_js,
        session_cookie_set_js,
    )

    go = _defer_nav_js(path)
    if clear_cookie:
        js = f"{browser_auth_logout_clear_js()} {go}"
    else:
        clear_js = session_cookie_clear_js()
        sk = getattr(request.session, "session_key", None) or ""
        storage_js = browser_session_storage_clear_js()
        if not sk:
            js = f"{storage_js} {go}"
        else:
            js = f"{storage_js} {clear_js} {session_cookie_set_js(sk)} {go}"
    return rx.call_script(js)


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
    #: When set, registers an extra handler that reads credentials from
    #: ``form_data`` (avoids stale bound state on fast submit). Keys default to
    #: ``username`` / ``password`` for HTML ``name=`` attributes.
    submit_form_event: str | None = "submit_login_form"
    form_username_key: str = "username"
    form_password_key: str = "password"
    login_fields: tuple[str, ...] = DEFAULT_LOGIN_FIELDS


def populate_session_auth_state(
    ns: dict[str, Any],
    cfg: SessionAuthConfig,
    *,
    cls_name: str,
    annotations: dict[str, type],
) -> None:
    """Add session login/logout fields and handlers to ``ns`` (flat state build)."""
    u_var = cfg.username_var
    p_var = cfg.password_var
    e_var = cfg.error_var
    post_in = cfg.post_login_redirect
    post_out = cfg.post_logout_redirect
    when_auth = cfg.redirect_when_authenticated
    msg_no_session = cfg.session_unavailable_message
    msg_bad = cfg.invalid_credentials_message
    form_u = cfg.form_username_key
    form_p = cfg.form_password_key
    login_fields = cfg.login_fields

    annotations[u_var] = str
    annotations[p_var] = str
    annotations[e_var] = str
    ns[u_var] = ""
    ns[p_var] = ""
    ns[e_var] = ""

    async def on_load_impl(self: Any) -> Any:
        from reflex_django.bridge.session_js import browser_auth_cookies_clear_js
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        if when_auth is None or not self.is_authenticated:
            return rx.call_script(browser_auth_cookies_clear_js())
        request = current_request()
        if request is None:
            return rx.call_script(_defer_nav_js(when_auth))
        return _sync_session_cookie_then_nav(request, when_auth)

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

    async def _finish_login(self: Any, request: Any) -> Any:
        from reflex_django.states.auth import (
            _mark_auth_ui_dirty,
            apply_auth_snapshot_to_state,
        )

        setattr(self, p_var, "")
        await session_async_save(request)
        sk = getattr(request.session, "session_key", None) or ""
        if sk:
            from reflex_django.bridge.session_js import mirror_auth_cookies_to_state_tree

            mirror_auth_cookies_to_state_tree(self, sk)
        await apply_auth_snapshot_to_state(self)
        _mark_auth_ui_dirty(self)
        return _sync_session_cookie_then_nav(request, post_in)

    async def submit_impl(self: Any) -> Any:
        setattr(self, e_var, "")
        request = current_request()
        if request is None:
            setattr(self, e_var, msg_no_session)
            return
        ok = await self.login(
            getattr(self, u_var),
            getattr(self, p_var),
            login_fields=login_fields,
        )
        if not ok:
            setattr(self, e_var, msg_bad)
            setattr(self, p_var, "")
            return
        return await _finish_login(self, request)

    ns[cfg.submit_event] = rx.event(submit_impl)

    if cfg.submit_form_event:

        async def submit_form_impl(self: Any, form_data: dict[str, Any]) -> Any:
            username = str(form_data.get(form_u, "")).strip()
            password = str(form_data.get(form_p, ""))
            setattr(self, u_var, username)
            setattr(self, p_var, password)
            setattr(self, e_var, "")
            request = current_request()
            if request is None:
                setattr(self, e_var, msg_no_session)
                return
            ok = await self.login(username, password, login_fields=login_fields)
            if not ok:
                setattr(self, e_var, msg_bad)
                setattr(self, p_var, "")
                return
            return await _finish_login(self, request)

        ns[cfg.submit_form_event] = rx.event(submit_form_impl)

    async def logout_impl(self: Any) -> Any:
        from reflex_django.bridge.session_js import browser_auth_logout_clear_js

        request = current_request()
        await AuthBridgeMixin.logout(self)
        if request is None:
            return rx.call_script(
                f"{browser_auth_logout_clear_js()} {_defer_nav_js(post_out)}"
            )
        return _sync_session_cookie_then_nav(request, post_out, clear_cookie=True)

    ns[cfg.logout_event] = rx.event(logout_impl)


def session_auth_mixin(
    cfg: SessionAuthConfig,
    *,
    base: type[rx.State] = DjangoUserState,
    state_module: str | None = None,
) -> type[rx.State]:
    """Build a concrete :class:`reflex.state.State` subclass with login/logout events.

    Uses :meth:`~reflex_django.states.auth.DjangoUserState.login` and
    :meth:`~reflex_django.states.auth.DjangoUserState.logout` (Django async session
    auth) and :func:`reflex_django.bridge.context.current_request` inside Reflex handlers.

    After successful login or logout, the mixin mirrors the session cookie into
    ``document.cookie`` (see :mod:`reflex_django.bridge.session_js`) and performs a
    short deferred full-page navigation. Reflex's synthetic request path does
    not run ``SessionMiddleware``, so ``rx.redirect`` alone often leaves the
    browser without an updated ``sessionid``.

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

    cls_name = cfg.state_class_name

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = state_mod
        annotations = dict(getattr(base, "__annotations__", {}))
        populate_session_auth_state(
            ns,
            cfg,
            cls_name=cls_name,
            annotations=annotations,
        )
        ns["__annotations__"] = annotations

    cls = types.new_class(cls_name, (base,), {}, exec_body)
    mod_obj = sys.modules.get(state_mod)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


__all__ = ["SessionAuthConfig", "populate_session_auth_state", "session_auth_mixin"]
