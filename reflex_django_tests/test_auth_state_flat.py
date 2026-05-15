"""Ensure :class:`DjangoAuthState` is a single flat Reflex substate."""

from __future__ import annotations

from reflex_django.conf import configure_django

configure_django()


def test_django_auth_state_is_single_substate_under_user() -> None:
    from reflex_django.auth.state import DjangoAuthState
    from reflex_django.auth_state import DjangoUserState

    assert DjangoAuthState.__name__ == "DjangoAuthState"
    assert DjangoAuthState.__bases__ == (DjangoUserState,)
    assert hasattr(DjangoAuthState, "login_error")
    assert hasattr(DjangoAuthState, "registration_error")
    assert hasattr(DjangoAuthState, "reset_error")
    assert hasattr(DjangoAuthState, "redirect_to_login")


def test_build_django_auth_state_returns_singleton() -> None:
    from reflex_django.auth.state import DjangoAuthState
    from reflex_django.auth.state_builders import build_django_auth_state

    assert build_django_auth_state() is DjangoAuthState
