"""Reflex-Django: run a Django backend alongside a Reflex app.

This package provides an opt-in plugin that mounts a Django ASGI application
(with Django ORM and Django Admin) on the same ASGI process as a Reflex app.
The Reflex Starlette + Socket.IO stack is kept unchanged; Django is routed at
configurable path prefixes (default: ``/admin`` for admin; optional
``backend_prefix`` for your own Django HTTP routes).

Typical usage in ``rxconfig.py``::

    import reflex as rx
    from reflex_django import ReflexDjangoPlugin

    config = rx.Config(
        app_name="myapp",
        plugins=[ReflexDjangoPlugin(settings_module="myapp.settings")],
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.asgi import build_django_asgi, make_dispatcher
from reflex_django.cli import django_cli
from reflex_django.conf import configure_django
from reflex_django.plugin import ReflexDjangoPlugin

if TYPE_CHECKING:
    from reflex_django.admin import register as register_admin
    from reflex_django.auth import (
        AuthSettings,
        DjangoAuthState,
        add_auth_pages,
        autoload,
        get_auth_settings,
        pages as auth_pages,
        login_required,
        routes as auth_routes,
    )
    from reflex_django.auth_state import DjangoUserState, user_snapshot
    from reflex_django.authz import (
        ReflexDjangoAuthError,
        auser_has_perm,
        django_login_required,
        require_login_user,
    )
    from reflex_django.context import (
        begin_event_request,
        current_language,
        current_request,
        current_session,
        current_user,
        end_event_request,
    )
    from reflex_django.i18n_state import DjangoI18nState
    from reflex_django.middleware import DjangoEventBridge
    from reflex_django.model import Model
    from reflex_django.reflex_context import (
        DjangoContextState,
        builtin_i18n_context,
        builtin_user_context,
        collect_reflex_context,
    )
    from reflex_django.session_js import (
        session_cookie_clear_js,
        session_cookie_name_and_suffix,
        session_cookie_set_js,
    )

__all__ = [
    "AuthSettings",
    "DjangoAuthState",
    "DjangoContextState",
    "DjangoEventBridge",
    "DjangoI18nState",
    "DjangoUserState",
    "Model",
    "ReflexDjangoAuthError",
    "ReflexDjangoPlugin",
    "add_auth_pages",
    "auth_pages",
    "auth_routes",
    "auser_has_perm",
    "autoload",
    "begin_event_request",
    "build_django_asgi",
    "builtin_i18n_context",
    "builtin_user_context",
    "collect_reflex_context",
    "configure_django",
    "current_language",
    "current_request",
    "current_session",
    "current_user",
    "django_cli",
    "django_login_required",
    "get_auth_settings",
    "end_event_request",
    "make_dispatcher",
    "register_admin",
    "login_required",
    "require_login_user",
    "session_cookie_clear_js",
    "session_cookie_name_and_suffix",
    "session_cookie_set_js",
    "user_snapshot",
]


# Lazy attribute access (PEP 562). The submodules listed below import the
# Django ORM, admin, or http machinery and therefore require
# ``django.setup()`` to have completed. Loading them eagerly from
# ``__init__.py`` would fail when Django imports this package during
# ``apps.populate()`` (e.g. if ``reflex_django`` is listed in
# ``INSTALLED_APPS``). Resolve them on first attribute access instead so the
# package can be safely imported at any time.
_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "DjangoContextState": ("reflex_django.reflex_context", "DjangoContextState"),
    "DjangoEventBridge": ("reflex_django.middleware", "DjangoEventBridge"),
    "DjangoI18nState": ("reflex_django.i18n_state", "DjangoI18nState"),
    "DjangoUserState": ("reflex_django.auth_state", "DjangoUserState"),
    "Model": ("reflex_django.model", "Model"),
    "ReflexDjangoAuthError": ("reflex_django.authz", "ReflexDjangoAuthError"),
    "auser_has_perm": ("reflex_django.authz", "auser_has_perm"),
    "begin_event_request": ("reflex_django.context", "begin_event_request"),
    "builtin_i18n_context": ("reflex_django.reflex_context", "builtin_i18n_context"),
    "builtin_user_context": ("reflex_django.reflex_context", "builtin_user_context"),
    "collect_reflex_context": (
        "reflex_django.reflex_context",
        "collect_reflex_context",
    ),
    "current_language": ("reflex_django.context", "current_language"),
    "current_request": ("reflex_django.context", "current_request"),
    "current_session": ("reflex_django.context", "current_session"),
    "current_user": ("reflex_django.context", "current_user"),
    "django_login_required": ("reflex_django.authz", "django_login_required"),
    "end_event_request": ("reflex_django.context", "end_event_request"),
    "AuthSettings": ("reflex_django.auth.settings", "AuthSettings"),
    "DjangoAuthState": ("reflex_django.auth.state", "DjangoAuthState"),
    "add_auth_pages": ("reflex_django.auth.registry", "add_auth_pages"),
    "auth_pages": ("reflex_django.auth", "pages"),
    "auth_routes": ("reflex_django.auth", "routes"),
    "autoload": ("reflex_django.auth.registry", "autoload"),
    "get_auth_settings": ("reflex_django.auth.settings", "get_auth_settings"),
    "register_admin": ("reflex_django.admin", "register"),
    "login_required": ("reflex_django.auth.decorators", "login_required"),
    "require_login_user": ("reflex_django.authz", "require_login_user"),
    "session_cookie_clear_js": ("reflex_django.session_js", "session_cookie_clear_js"),
    "session_cookie_name_and_suffix": (
        "reflex_django.session_js",
        "session_cookie_name_and_suffix",
    ),
    "session_cookie_set_js": ("reflex_django.session_js", "session_cookie_set_js"),
    "user_snapshot": ("reflex_django.auth_state", "user_snapshot"),
}


def __getattr__(name: str) -> Any:
    """Resolve lazy public attributes on first access.

    Args:
        name: The attribute being requested on the ``reflex_django`` package.

    Returns:
        The resolved attribute value.

    Raises:
        AttributeError: If ``name`` is not a known public attribute.
    """
    target = _LAZY_ATTRS.get(name)
    if target is None:
        msg = f"module 'reflex_django' has no attribute {name!r}"
        raise AttributeError(msg)

    from importlib import import_module

    module = import_module(target[0])
    value = getattr(module, target[1])
    globals()[name] = value
    return value
