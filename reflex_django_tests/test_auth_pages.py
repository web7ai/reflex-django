"""Tests for extensible auth page hooks."""

from __future__ import annotations

import reflex as rx
from django.conf import settings

from reflex_django.setup.conf import configure_django

configure_django()


def test_login_page_heading_text_from_messages(monkeypatch) -> None:
    from reflex_django.auth.pages import LoginPage

    monkeypatch.setattr(
        settings,
        "REFLEX_DJANGO_AUTH",
        {"MESSAGES": {"login_heading": "Welcome back"}},
        raising=False,
    )
    assert LoginPage.heading_text() == "Welcome back"


def test_branded_login_subclass_heading() -> None:
    from reflex_django.auth.pages import LoginPage

    class BrandedLogin(LoginPage):
        @classmethod
        def heading_text(cls) -> str:
            return "Branded"

    assert BrandedLogin.heading_text() == "Branded"
    component = BrandedLogin.render()
    assert component is not None


def test_into_component_login_page() -> None:
    from reflex.compiler.compiler import into_component

    from reflex_django.auth.pages import LoginPage

    compiled = into_component(LoginPage)
    assert compiled is not None


def test_login_page_uses_state_cls_submit_handler() -> None:
    from reflex_django.auth.pages import LoginPage
    from reflex_django.auth.state import DjangoAuthState

    assert LoginPage.get_state() is DjangoAuthState
    assert LoginPage.state_cls is None
    form = LoginPage.form_body(LoginPage.auth_settings())
    assert form is not None


def test_register_login_page_uses_subclass_default_on_load() -> None:
    from reflex_django.auth.pages import LoginPage
    from reflex_django.auth.registry import register_login_page
    from reflex_django.auth.settings import AuthSettings
    from reflex_django.auth.state import DjangoAuthState

    class CustomLogin(LoginPage):
        default_on_load = DjangoAuthState.sync_from_django

    app = rx.App()
    auth = AuthSettings(enabled=True, login_url="/custom")
    register_login_page(app, page=CustomLogin, settings=auth)
    entry = app._unevaluated_pages["custom"]
    assert entry.on_load is DjangoAuthState.sync_from_django


def test_password_reset_page_default_on_load_is_none() -> None:
    from reflex_django.auth.pages import PasswordResetPage

    assert PasswordResetPage.default_on_load is None
