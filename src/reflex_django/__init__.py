"""Reflex-Django: mount a Reflex SPA in Django with a shared event bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.asgi.app import build_django_asgi
from reflex_django.cli import django_cli
from reflex_django.setup.conf import configure_django
from reflex_django.runtime.app_factory import create_app
from reflex_django.setup.plugin import ReflexDjangoPlugin, make_dispatcher

if TYPE_CHECKING:
    from reflex_django.django.admin import register as register_admin
    from reflex_django.auth import (
        AuthPageMeta,
        AuthSettings,
        BaseAuthPage,
        LoginPage,
        PasswordResetConfirmPage,
        PasswordResetPage,
        ReflexDjangoAuthError,
        RegisterPage,
        add_auth_pages,
        auser_has_perm,
        autoload,
        get_auth_settings,
        login_required,
        permission_required,
        pages as auth_pages,
        register_login_page,
        register_password_reset_confirm_page,
        register_password_reset_page,
        register_register_page,
        require_login_user,
        routes as auth_routes,
    )
    from reflex_django.auth_state import user_snapshot
    from reflex_django.serializers import ReflexDjangoModelSerializer
    from reflex_django.bridge.context import (
        begin_event_request,
        begin_event_response,
        current_csrf_token,
        current_language,
        current_messages,
        current_request,
        current_response,
        current_session,
        current_user,
        end_event_request,
        end_event_response,
    )
    from reflex_django.bridge.event_handler import run_middleware_chain
    from reflex_django.bridge.request import RequestProxy, request
    from reflex_django.bridge.django_event import DjangoEventBridge
    from reflex_django.django.model import Model
    from reflex_django.bridge.session_js import (
        session_cookie_clear_js,
        session_cookie_name_and_suffix,
        session_cookie_set_js,
    )

__all__ = [
    "AuthSettings",
    "DjangoEventBridge",
    "Model",
    "ReflexDjangoAuthError",
    "ReflexDjangoModelSerializer",
    "ReflexDjangoPlugin",
    "add_auth_pages",
    "auth_pages",
    "auth_routes",
    "auser_has_perm",
    "autoload",
    "begin_event_request",
    "begin_event_response",
    "build_django_asgi",
    "app",
    "configure_django",
    "create_app",
    "current_csrf_token",
    "current_language",
    "current_messages",
    "current_request",
    "current_response",
    "current_session",
    "current_user",
    "django_cli",
    "end_event_request",
    "end_event_response",
    "get_auth_settings",
    "make_dispatcher",
    "register_admin",
    "login_required",
    "permission_required",
    "request",
    "RequestProxy",
    "require_login_user",
    "run_middleware_chain",
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
    "app": ("reflex_django.runtime.reflex_app", "app"),
    "begin_event_response": ("reflex_django.bridge.context", "begin_event_response"),
    "current_csrf_token": ("reflex_django.bridge.context", "current_csrf_token"),
    "current_messages": ("reflex_django.bridge.context", "current_messages"),
    "current_response": ("reflex_django.bridge.context", "current_response"),
    "end_event_response": ("reflex_django.bridge.context", "end_event_response"),
    "run_middleware_chain": (
        "reflex_django.bridge.event_handler",
        "run_middleware_chain",
    ),
    "ReflexDjangoModelSerializer": (
        "reflex_django.serializers",
        "ReflexDjangoModelSerializer",
    ),
    "DjangoEventBridge": ("reflex_django.bridge.django_event", "DjangoEventBridge"),
    "Model": ("reflex_django.django.model", "Model"),
    "ReflexDjangoAuthError": ("reflex_django.auth.shortcuts", "ReflexDjangoAuthError"),
    "auser_has_perm": ("reflex_django.auth.shortcuts", "auser_has_perm"),
    "begin_event_request": ("reflex_django.bridge.context", "begin_event_request"),
    "current_language": ("reflex_django.bridge.context", "current_language"),
    "current_request": ("reflex_django.bridge.context", "current_request"),
    "current_session": ("reflex_django.bridge.context", "current_session"),
    "current_user": ("reflex_django.bridge.context", "current_user"),
    "end_event_request": ("reflex_django.bridge.context", "end_event_request"),
    "request": ("reflex_django.bridge.request", "request"),
    "RequestProxy": ("reflex_django.bridge.request", "RequestProxy"),
    "AuthSettings": ("reflex_django.auth.settings", "AuthSettings"),
    "add_auth_pages": ("reflex_django.auth.registry", "add_auth_pages"),
    "auth_pages": ("reflex_django.auth", "pages"),
    "auth_routes": ("reflex_django.auth", "routes"),
    "autoload": ("reflex_django.auth.registry", "autoload"),
    "AuthPageMeta": ("reflex_django.auth.pages.base", "AuthPageMeta"),
    "BaseAuthPage": ("reflex_django.auth.pages.base", "BaseAuthPage"),
    "LoginPage": ("reflex_django.auth.pages", "LoginPage"),
    "PasswordResetConfirmPage": (
        "reflex_django.auth.pages",
        "PasswordResetConfirmPage",
    ),
    "PasswordResetPage": ("reflex_django.auth.pages", "PasswordResetPage"),
    "RegisterPage": ("reflex_django.auth.pages", "RegisterPage"),
    "register_login_page": ("reflex_django.auth.registry", "register_login_page"),
    "register_password_reset_confirm_page": (
        "reflex_django.auth.registry",
        "register_password_reset_confirm_page",
    ),
    "register_password_reset_page": (
        "reflex_django.auth.registry",
        "register_password_reset_page",
    ),
    "register_register_page": (
        "reflex_django.auth.registry",
        "register_register_page",
    ),
    "get_auth_settings": ("reflex_django.auth.settings", "get_auth_settings"),
    "register_admin": ("reflex_django.django.admin", "register"),
    "login_required": ("reflex_django.auth.decorators", "login_required"),
    "permission_required": ("reflex_django.auth.decorators", "permission_required"),
    "require_login_user": ("reflex_django.auth.shortcuts", "require_login_user"),
    "session_cookie_clear_js": ("reflex_django.bridge.session_js", "session_cookie_clear_js"),
    "session_cookie_name_and_suffix": (
        "reflex_django.bridge.session_js",
        "session_cookie_name_and_suffix",
    ),
    "session_cookie_set_js": ("reflex_django.bridge.session_js", "session_cookie_set_js"),
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
