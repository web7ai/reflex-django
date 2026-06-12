"""Ensure :class:`DjangoAuthState` is a single flat Reflex substate."""

from __future__ import annotations

from reflex_django.setup.conf import configure_django

configure_django()


def test_django_auth_state_is_single_substate_under_user() -> None:
    import reflex as rx

    from reflex_django.auth.state import DjangoAuthState
    from reflex_django.state.auth_bridge import AuthBridgeMixin

    assert DjangoAuthState.__name__ == "DjangoAuthState"
    assert DjangoAuthState.__bases__ == (AuthBridgeMixin, rx.State)
    assert hasattr(DjangoAuthState, "login_error")
    assert hasattr(DjangoAuthState, "registration_error")
    assert hasattr(DjangoAuthState, "reset_error")
    assert hasattr(DjangoAuthState, "redirect_to_login")
    assert hasattr(DjangoAuthState, "sync_auth_ui")
    assert hasattr(DjangoAuthState, "sync_from_django")
    assert hasattr(DjangoAuthState, "refresh_django_user_fields")
    assert hasattr(DjangoAuthState, "is_authenticated")
    assert "is_authenticated" in DjangoAuthState.computed_vars
    assert "is_authenticated" not in DjangoAuthState.inherited_vars


def test_build_django_auth_state_returns_singleton() -> None:
    from reflex_django.auth.state import DjangoAuthState
    from reflex_django.auth.state_builders import build_django_auth_state

    assert build_django_auth_state() is DjangoAuthState
