"""Build a flat :class:`DjangoAuthState` (single Reflex substate, no nested mixins)."""

from __future__ import annotations

import sys
import types
from typing import Any

from reflex_django.auth.mixins.navigation import populate_navigation_state
from reflex_django.auth.mixins.password_reset import (
    PasswordResetConfig,
    populate_password_reset_state,
)
from reflex_django.auth.mixins.registration import (
    RegistrationConfig,
    populate_registration_state,
)
from reflex_django.auth.settings import AuthSettings, get_auth_settings
from reflex_django.auth_state import DjangoUserState
from reflex_django.mixins.session_auth import SessionAuthConfig, populate_session_auth_state

_STATE_MODULE = "reflex_django.auth.state"


def build_django_auth_state(*, auth: AuthSettings | None = None) -> type:
    """Return one ``DjangoAuthState`` class with all auth fields and events.

    Reflex treats each dynamically subclassed :class:`reflex.state.State` as its
    own substate. Chaining mixins with repeated class names produced nested
    ``DjangoAuthState`` substates that failed on socket connect. This builder
    merges every mixin into a single class that extends :class:`DjangoUserState`.
    """
    mod = sys.modules.get(_STATE_MODULE)
    if mod is not None:
        existing = getattr(mod, "DjangoAuthState", None)
        if existing is not None:
            return existing

    auth = auth or get_auth_settings()
    session_cfg = SessionAuthConfig(
        post_login_redirect=auth.login_redirect_url,
        post_logout_redirect=auth.logout_redirect_url,
        redirect_when_authenticated=auth.redirect_authenticated_user,
        invalid_credentials_message=auth.messages["invalid_credentials"],
        login_fields=auth.login_fields,
        state_class_name="DjangoAuthState",
    )
    reg_cfg = RegistrationConfig.from_auth_settings(auth)
    reset_cfg = PasswordResetConfig.from_auth_settings(auth)
    cls_name = "DjangoAuthState"

    def exec_body(ns: dict[str, Any]) -> None:
        ns["__module__"] = _STATE_MODULE
        annotations: dict[str, type] = dict(
            getattr(DjangoUserState, "__annotations__", {})
        )
        populate_session_auth_state(
            ns,
            session_cfg,
            cls_name=cls_name,
            annotations=annotations,
        )
        populate_registration_state(
            ns,
            reg_cfg,
            cls_name=cls_name,
            annotations=annotations,
        )
        populate_password_reset_state(
            ns,
            reset_cfg,
            cls_name=cls_name,
            annotations=annotations,
        )
        populate_navigation_state(ns, cls_name=cls_name)
        ns["__annotations__"] = annotations

    cls = types.new_class(cls_name, (DjangoUserState,), {}, exec_body)
    mod_obj = sys.modules.get(_STATE_MODULE)
    if mod_obj is not None:
        setattr(mod_obj, cls.__name__, cls)
    return cls


def get_or_create_django_auth_state() -> type:
    """Return the module singleton ``DjangoAuthState`` class."""
    mod = sys.modules.get(_STATE_MODULE)
    if mod is not None:
        existing = getattr(mod, "DjangoAuthState", None)
        if existing is not None:
            return existing
    cls = build_django_auth_state()
    cls.__name__ = "DjangoAuthState"
    cls.__qualname__ = "DjangoAuthState"
    mod_obj = sys.modules.get(_STATE_MODULE)
    if mod_obj is not None:
        setattr(mod_obj, "DjangoAuthState", cls)
    return cls


__all__ = ["build_django_auth_state", "get_or_create_django_auth_state"]
