"""Canonical :class:`DjangoAuthState` for canned auth pages."""

from __future__ import annotations

import sys
from typing import Any

from reflex_django.auth.mixins.navigation import navigation_mixin
from reflex_django.auth.mixins.password_reset import (
    PasswordResetConfig,
    password_reset_mixin,
)
from reflex_django.auth.mixins.registration import (
    RegistrationConfig,
    registration_mixin,
)
from reflex_django.auth.settings import get_auth_settings
from reflex_django.auth_state import DjangoUserState
from reflex_django.mixins.session_auth import SessionAuthConfig, session_auth_mixin

_STATE_MODULE = "reflex_django.auth.state"


def _build_django_auth_state() -> type:
    auth = get_auth_settings()
    session_cfg = SessionAuthConfig(
        post_login_redirect=auth.login_redirect_url,
        post_logout_redirect=auth.logout_redirect_url,
        redirect_when_authenticated=auth.redirect_authenticated_user,
        invalid_credentials_message=auth.messages["invalid_credentials"],
        state_class_name="_DjangoAuthSessionPart",
    )
    session_part = session_auth_mixin(
        session_cfg,
        base=DjangoUserState,
        state_module=_STATE_MODULE,
    )
    reg_part = registration_mixin(
        RegistrationConfig.from_auth_settings(auth),
        base=session_part,
        state_module=_STATE_MODULE,
    )
    reset_part = password_reset_mixin(
        PasswordResetConfig.from_auth_settings(auth),
        base=reg_part,
        state_module=_STATE_MODULE,
    )
    return navigation_mixin(
        base=reset_part,
        state_module=_STATE_MODULE,
        state_class_name="DjangoAuthState",
    )


def _get_django_auth_state() -> type:
    mod = sys.modules.get(_STATE_MODULE)
    if mod is not None:
        existing = getattr(mod, "DjangoAuthState", None)
        if existing is not None:
            return existing
    cls = _build_django_auth_state()
    cls.__name__ = "DjangoAuthState"
    cls.__qualname__ = "DjangoAuthState"
    mod_obj = sys.modules.get(_STATE_MODULE)
    if mod_obj is not None:
        setattr(mod_obj, "DjangoAuthState", cls)
    return cls


DjangoAuthState = _get_django_auth_state()

__all__ = ["DjangoAuthState"]
