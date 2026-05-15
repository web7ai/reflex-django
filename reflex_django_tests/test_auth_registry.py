"""Tests for :mod:`reflex_django.auth.registry`."""

from __future__ import annotations

import reflex as rx
from django.conf import settings

from reflex_django.conf import configure_django

configure_django()


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
    routes = set(app._unevaluated_pages)

    def _norm(path: str) -> str:
        return path.strip("/")

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
    routes = set(app._unevaluated_pages)

    def _norm(path: str) -> str:
        return path.strip("/")

    assert _norm(auth.login_url) in routes
    assert _norm(auth.signup_url) not in routes
    assert _norm(auth.password_reset_url) not in routes


def test_add_auth_pages_skips_when_disabled() -> None:
    from reflex_django.auth.registry import add_auth_pages
    from reflex_django.auth.settings import AuthSettings

    app = rx.App()
    add_auth_pages(app, settings=AuthSettings(enabled=False))
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
