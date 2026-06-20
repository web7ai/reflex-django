"""Build a flat :class:`DjangoAuthState` (single Reflex substate, no nested mixins)."""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import reflex as rx

from reflex_django.auth.mixins.navigation import populate_navigation_state
from reflex_django.auth.settings import AuthSettings, get_auth_settings
from reflex_django.setup.conf import configure_django
from reflex_django.mixins.session_auth import (
    SessionAuthConfig,
    populate_session_auth_state,
)
from reflex_django.state.auth_bridge import AuthBridgeMixin

# Snapshot fields owned on ``DjangoAuthState`` (``is_authenticated`` is a ``@rx.var``).
_AUTH_SNAPSHOT_DEFAULTS: dict[str, Any] = {
    "user_id": None,
    "username": "",
    "email": "",
    "first_name": "",
    "last_name": "",
    "is_staff": False,
    "is_superuser": False,
    "group_names": [],
    "messages": [],
    "csrf_token": "",
    "language": "",
    "language_bidi": False,
}


def _django_user_snapshot_annotations() -> dict[str, Any]:
    """Concrete field types for dynamic ``DjangoAuthState``.

    ``DjangoUserState`` uses PEP 563 annotations; copying ``__annotations__``
    leaves ``ForwardRef`` values that Reflex ``Field()`` cannot resolve.
    """
    return {
        "user_id": int | None,
        "username": str,
        "email": str,
        "first_name": str,
        "last_name": str,
        "is_staff": bool,
        "is_superuser": bool,
        "group_names": list[str],
        "messages": list[dict[str, Any]],
        "csrf_token": str,
        "language": str,
        "language_bidi": bool,
    }


_STATE_MODULE = "reflex_django.auth.state"


def _auth_state_module() -> types.ModuleType:
    """Return ``reflex_django.auth.state``, loading it if needed."""
    return importlib.import_module(_STATE_MODULE)


def _cached_auth_state_class(mod: types.ModuleType | None = None) -> type | None:
    """Read ``DjangoAuthState`` from the module dict without triggering ``__getattr__``."""
    mod = mod or sys.modules.get(_STATE_MODULE)
    if mod is None:
        return None
    existing = mod.__dict__.get("DjangoAuthState")
    return existing if isinstance(existing, type) else None


def _store_auth_state_class(cls: type) -> None:
    mod_obj = _auth_state_module()
    setattr(mod_obj, "DjangoAuthState", cls)


def build_django_auth_state(*, auth: AuthSettings | None = None) -> type:
    """Return one ``DjangoAuthState`` class with all auth fields and events.

    Reflex treats each dynamically subclassed :class:`reflex.state.State` as its
    own substate. Chaining mixins with repeated class names produced nested
    ``DjangoAuthState`` substates that failed on socket connect. This builder
    merges every mixin into a single class. ``is_authenticated`` is a live
    :func:`~reflex.var` (see navigation mixin), not an inherited snapshot field.
    """
    configure_django()

    from reflex_django.auth.mixins.password_reset import (
        PasswordResetConfig,
        populate_password_reset_state,
    )
    from reflex_django.auth.mixins.registration import (
        RegistrationConfig,
        populate_registration_state,
    )

    existing = _cached_auth_state_class()
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
        ns["_rx_bridge"] = "full"
        annotations = _django_user_snapshot_annotations()
        ns.update(_AUTH_SNAPSHOT_DEFAULTS)

        @rx.event
        async def sync_from_django(
            self: Any,
            *,
            include_groups: bool | None = None,
        ) -> None:
            from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

            await _sync_auth_snapshots_in_tree(self, include_groups=include_groups)

        ns["sync_from_django"] = sync_from_django
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
        populate_navigation_state(ns, cls_name=cls_name, annotations=annotations)
        ns["__annotations__"] = annotations

    cls = types.new_class(cls_name, (AuthBridgeMixin, rx.State), {}, exec_body)
    _store_auth_state_class(cls)
    return cls


def get_or_create_django_auth_state() -> type:
    """Return the module singleton ``DjangoAuthState`` class."""
    existing = _cached_auth_state_class()
    if existing is not None:
        return existing
    cls = build_django_auth_state()
    cls.__name__ = "DjangoAuthState"
    cls.__qualname__ = "DjangoAuthState"
    _store_auth_state_class(cls)
    return cls


__all__ = ["build_django_auth_state", "get_or_create_django_auth_state"]
