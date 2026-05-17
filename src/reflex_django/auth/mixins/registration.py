"""Registration mixin for Django user signup in Reflex state."""

from __future__ import annotations

import inspect
import sys
import types
from dataclasses import dataclass
from typing import Any

import reflex as rx
from asgiref.sync import sync_to_async
from django.contrib.auth import alogin, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from reflex_django.auth.settings import AuthSettings
from reflex_django.context import current_request
from reflex_django.mixins.session_auth import _sync_session_cookie_then_nav
from reflex_django.state.auth_bridge import session_async_save


@dataclass(frozen=True)
class RegistrationConfig:
    """Registration form and redirect settings."""

    signup_redirect_url: str = "/login"
    redirect_when_authenticated: str = "/"
    email_required: bool = False
    username_min_length: int = 1
    password_min_length: int = 8
    error_var: str = "registration_error"
    success_var: str = "registration_success"
    on_load_event: str = "on_load_register"
    submit_event: str = "handle_registration"
    state_class_name: str = "DjangoAuthState"
    messages: dict[str, str] | None = None

    @classmethod
    def from_auth_settings(cls, auth: AuthSettings) -> RegistrationConfig:
        return cls(
            signup_redirect_url=auth.signup_redirect_url,
            redirect_when_authenticated=auth.redirect_authenticated_user,
            email_required=auth.email_required,
            username_min_length=auth.username_min_length,
            password_min_length=auth.password_min_length,
            messages=auth.messages,
        )


def _msg(cfg: RegistrationConfig, key: str, default: str) -> str:
    if cfg.messages and key in cfg.messages:
        return cfg.messages[key]
    return default


def populate_registration_state(
    ns: dict[str, Any],
    cfg: RegistrationConfig,
    *,
    cls_name: str,
    annotations: dict[str, type],
) -> None:
    """Add registration fields and handlers to ``ns`` (flat state build)."""
    e_var = cfg.error_var
    s_var = cfg.success_var
    when_auth = cfg.redirect_when_authenticated
    post_signup = cfg.signup_redirect_url
    min_user = cfg.username_min_length
    min_pass = cfg.password_min_length
    email_req = cfg.email_required

    annotations[e_var] = str
    annotations[s_var] = bool
    ns[e_var] = ""
    ns[s_var] = False

    async def on_load_register_impl(self: Any) -> Any:
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self)
        if when_auth is None or not self.is_authenticated:
            return None
        request = current_request()
        if request is None:
            from reflex_django.mixins.session_auth import _defer_nav_js

            return rx.call_script(_defer_nav_js(when_auth))
        return _sync_session_cookie_then_nav(request, when_auth)

    ns[cfg.on_load_event] = rx.event(on_load_register_impl)

    async def handle_registration_impl(self: Any, form_data: dict[str, Any]) -> Any:
        setattr(self, e_var, "")
        setattr(self, s_var, False)
        username = str(form_data.get("username", "")).strip()
        email = str(form_data.get("email", "")).strip()
        password = str(form_data.get("password", ""))
        confirm = str(form_data.get("confirm_password", ""))

        if len(username) < min_user:
            setattr(
                self,
                e_var,
                _msg(cfg, "username_required", "Username is required."),
            )
            return
        if email_req and not email:
            setattr(
                self,
                e_var,
                _msg(cfg, "email_required", "Email is required."),
            )
            return
        if password != confirm:
            setattr(
                self,
                e_var,
                _msg(cfg, "password_mismatch", "Passwords do not match."),
            )
            return
        if len(password) < min_pass:
            setattr(
                self,
                e_var,
                _msg(cfg, "password_too_short", "Password is too short."),
            )
            return

        user_model = get_user_model()

        def _username_exists() -> bool:
            return user_model.objects.filter(username=username).exists()

        def _email_exists() -> bool:
            if not email:
                return False
            return user_model.objects.filter(email__iexact=email).exists()

        if await sync_to_async(_username_exists)():
            setattr(
                self,
                e_var,
                _msg(cfg, "username_taken", "That username is already taken."),
            )
            return
        if email and await sync_to_async(_email_exists)():
            setattr(
                self,
                e_var,
                _msg(cfg, "email_taken", "That email is already registered."),
            )
            return

        def _validate_pw() -> None:
            validate_password(password, user=user_model(username=username))

        try:
            await sync_to_async(_validate_pw)()
        except ValidationError as exc:
            setattr(self, e_var, " ".join(exc.messages))
            return

        request = current_request()
        if request is None:
            setattr(self, e_var, "Session unavailable. Reload the page.")
            return

        def _create_user() -> Any:
            user = user_model(username=username, email=email or "")
            user.set_password(password)
            user.save()
            return user

        user = await sync_to_async(_create_user)()
        await alogin(request, user)
        await session_async_save(request)
        await self.refresh_django_user_fields()
        setattr(self, s_var, True)
        return _sync_session_cookie_then_nav(request, post_signup)

    ns[cfg.submit_event] = rx.event(handle_registration_impl)


def registration_mixin(
    cfg: RegistrationConfig,
    *,
    base: type[rx.State],
    state_module: str | None = None,
) -> type[rx.State]:
    """Extend ``base`` with registration event handlers."""
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
        populate_registration_state(
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
