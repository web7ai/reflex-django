"""Tests for :mod:`reflex_django.mixins.session_auth`."""

from __future__ import annotations

import sys

import reflex as rx

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.states.auth import DjangoUserState  # noqa: E402
from reflex_django.mixins.session_auth import SessionAuthConfig, session_auth_mixin  # noqa: E402

class _AppStub(rx.State):
    app_flag: bool = False


def test_session_auth_mixin_builds_state_and_registers_module() -> None:
    cfg = SessionAuthConfig(
        post_login_redirect="/notes",
        post_logout_redirect="/login",
        redirect_when_authenticated="/notes",
    )
    Cls = session_auth_mixin(cfg, state_module=__name__)
    assert issubclass(Cls, rx.State)
    assert issubclass(Cls, DjangoUserState)
    assert Cls.__name__ == "SessionAuthState"
    assert Cls.__module__ == __name__
    ann = Cls.__annotations__
    assert ann["login_username"] is str
    assert ann["login_password"] is str
    assert ann["login_error"] is str
    assert hasattr(Cls, "on_load_login")
    assert hasattr(Cls, "submit_login")
    assert hasattr(Cls, "submit_login_form")
    assert hasattr(Cls, "logout")
    assert hasattr(Cls, "set_login_username")
    assert hasattr(Cls, "set_login_password")
    assert getattr(sys.modules[__name__], Cls.__name__) is Cls


def test_session_auth_mixin_accepts_custom_base() -> None:
    cfg = SessionAuthConfig()
    Cls = session_auth_mixin(cfg, base=_AppStub, state_module=__name__)
    assert issubclass(Cls, _AppStub)
    assert issubclass(Cls, rx.State)


def test_session_auth_mixin_custom_field_and_event_names() -> None:
    cfg = SessionAuthConfig(
        username_var="u",
        password_var="p",
        error_var="err",
        on_load_event="ol",
        submit_event="sub",
        logout_event="lo",
        submit_form_event=None,
        state_class_name="SessionAuthAltState",
    )
    Cls = session_auth_mixin(cfg, base=_AppStub, state_module=__name__)
    assert Cls.__name__ == "SessionAuthAltState"
    ann = Cls.__annotations__
    assert ann["u"] is str and ann["p"] is str and ann["err"] is str
    assert hasattr(Cls, "ol")
    assert hasattr(Cls, "sub")
    assert hasattr(Cls, "lo")
    assert hasattr(Cls, "set_u")
    assert hasattr(Cls, "set_p")
    assert not hasattr(Cls, "submit_login_form")


def test_session_auth_logout_handler_calls_auth_bridge() -> None:
    """Default ``logout`` event must delegate to AuthBridgeMixin (not ``self.logout()``)."""
    import inspect

    from reflex_django.mixins import session_auth as mod

    src = inspect.getsource(mod.populate_session_auth_state)
    assert "AuthBridgeMixin.logout(self)" in src
    assert "await self.logout()" not in src


def test_mixins_package_reexports_session_auth() -> None:
    from reflex_django.mixins import SessionAuthConfig as SAC
    from reflex_django.mixins import session_auth_mixin as sam

    assert SAC is SessionAuthConfig
    assert sam is session_auth_mixin
