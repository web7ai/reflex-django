"""Register canned auth pages on a Reflex app."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.auth.pages import (
    login_page,
    password_reset_confirm_page,
    password_reset_page,
    register_page,
)
from reflex_django.auth.settings import AuthSettings, get_auth_settings
from reflex_django.auth.state import DjangoAuthState

if TYPE_CHECKING:
    from reflex.app import App


def add_auth_pages(app: App, *, settings: AuthSettings | None = None) -> None:
    """Add login, register, and password-reset pages from Django settings.

    Args:
        app: The Reflex application instance.
        settings: Optional pre-resolved settings; defaults to
            :func:`get_auth_settings`.
    """
    auth = settings or get_auth_settings()
    if not auth.enabled:
        return

    app.add_page(
        login_page,
        route=auth.login_url,
        title="Sign in",
        on_load=DjangoAuthState.on_load_login,
    )

    if auth.signup_enabled:
        app.add_page(
            register_page,
            route=auth.signup_url,
            title="Create account",
            on_load=DjangoAuthState.on_load_register,
        )

    if auth.password_reset_enabled:
        app.add_page(
            password_reset_page,
            route=auth.password_reset_url,
            title="Reset password",
        )
        app.add_page(
            password_reset_confirm_page,
            route=auth.password_reset_confirm_url,
            title="Set new password",
            on_load=DjangoAuthState.on_load_password_reset_confirm,
        )


def autoload() -> None:
    """Register auth pages on the app from ``rxconfig`` if importable.

    Intended for advanced setups; prefer calling :func:`add_auth_pages` explicitly
    in your app module.
    """
    from reflex_base.config import get_config

    app_name = get_config().app_name
    mod = __import__(app_name, fromlist=[app_name])
    app = getattr(mod, "app", None)
    if app is None:
        msg = f"Could not find rx.App in {app_name}.{app_name}"
        raise RuntimeError(msg)
    add_auth_pages(app)


__all__ = ["add_auth_pages", "autoload"]
