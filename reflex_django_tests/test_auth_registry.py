"""Tests for :mod:`reflex_django.auth.registry`."""

from __future__ import annotations

import reflex as rx
from django.conf import settings

from reflex_django.conf import configure_django

configure_django()


def _norm(path: str) -> str:
    return path.strip("/")


def _routes(app: rx.App) -> set[str]:
    return {_norm(p) for p in app._unevaluated_pages}


def test_add_auth_pages_registers_routes(monkeypatch) -> None:
    from reflex_django.auth.registry import add_auth_pages
    from reflex_django.auth.settings import AuthSettings

    app = rx.App()
    auth = AuthSettings(
        enabled=True,
        signup_enabled=True,
        password_reset_enabled=True,
    )
    add_auth_pages(app, settings=auth)

    routes = _routes(app)
    assert _norm(auth.login_url) in routes
    assert _norm(auth.signup_url) in routes
    assert _norm(auth.password_reset_url) in routes
    assert _norm(auth.password_reset_confirm_url) in routes


def test_add_auth_pages_respects_disabled_flags(monkeypatch) -> None:
    from reflex_django.auth.registry import add_auth_pages
    from reflex_django.auth.settings import AuthSettings

    app = rx.App()
    auth = AuthSettings(
        enabled=True,
        signup_enabled=False,
        password_reset_enabled=False,
    )
    add_auth_pages(app, settings=auth)
    routes = _routes(app)

    assert _norm(auth.login_url) in routes
    assert _norm(auth.signup_url) not in routes
    assert _norm(auth.password_reset_url) not in routes


def test_add_auth_pages_skips_when_disabled() -> None:
    from reflex_django.auth.registry import add_auth_pages
    from reflex_django.auth.settings import AuthSettings

    app = rx.App()
    add_auth_pages(app, settings=AuthSettings(enabled=False))
    assert len(app._unevaluated_pages) == 0


def test_register_login_page_with_custom_subclass() -> None:
    from reflex_django.auth.pages import LoginPage
    from reflex_django.auth.registry import register_login_page
    from reflex_django.auth.settings import AuthSettings
    from reflex_django.auth.state import DjangoAuthState

    class CustomLogin(LoginPage):
        @classmethod
        def render(cls) -> rx.Component:
            return rx.heading("Custom login")

    app = rx.App()
    auth = AuthSettings(enabled=True, login_url="/my-login")
    register_login_page(
        app,
        page=CustomLogin,
        route="/my-login",
        settings=auth,
    )
    routes = _routes(app)
    assert "my-login" in routes
    page_entry = app._unevaluated_pages["my-login"]
    assert page_entry.component is CustomLogin


def test_manual_add_page_without_add_auth_pages() -> None:
    from reflex_django.auth.pages import LoginPage
    from reflex_django.auth.state import DjangoAuthState

    app = rx.App()
    app.add_page(
        LoginPage,
        route="/custom-login",
        title="Sign in",
        on_load=DjangoAuthState.on_load_login,
    )
    routes = _routes(app)
    assert "custom-login" in routes
    assert len(routes) == 1


def test_login_page_is_callable_alias() -> None:
    from reflex.compiler.compiler import into_component

    from reflex_django.auth.pages import LoginPage, login_page

    assert login_page is LoginPage
    component = LoginPage()
    assert component is not None
    compiled = into_component(LoginPage)
    assert compiled is not None


def test_subclass_page_call_returns_component() -> None:
    from reflex_django.auth.pages import LoginPage

    class BrandedLogin(LoginPage):
        @classmethod
        def render(cls) -> rx.Component:
            return rx.heading("Branded")

    assert BrandedLogin() is not None
    assert BrandedLogin.render() is not None


def test_register_login_page_skips_when_disabled() -> None:
    from reflex_django.auth.registry import register_login_page
    from reflex_django.auth.settings import AuthSettings

    app = rx.App()
    register_login_page(app, settings=AuthSettings(enabled=False))
    assert len(app._unevaluated_pages) == 0


def test_routes_lazy_from_settings(monkeypatch) -> None:
    import reflex_django.auth.routes as auth_routes

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {"LOGIN_URL": "/custom-login", "SIGNUP_URL": "/custom-register"},
        raising=False,
    )
    assert auth_routes.LOGIN_ROUTE == "/custom-login"
    assert auth_routes.SIGNUP_ROUTE == "/custom-register"
