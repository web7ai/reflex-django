"""Regression tests for import-time circular dependencies."""

from __future__ import annotations

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.auth.registry import add_auth_pages  # noqa: E402
from reflex_django.states.auth import DjangoUserState  # noqa: E402
from reflex_django.state import ModelState  # noqa: E402


def test_auth_pages_import_without_cycle() -> None:
    """Loading auth pages must not cycle through state.model_state -> states -> auth_state."""
    assert callable(add_auth_pages)


def test_auth_state_imports_before_model_state() -> None:
    assert DjangoUserState is not None
    assert ModelState is not None


def test_auth_registry_import_before_django_setup() -> None:
    """Importing registry must not load Django models before configure_django."""
    from reflex_django.auth.registry import add_auth_pages

    assert callable(add_auth_pages)


def test_auth_state_module_import_without_accessing_class() -> None:
    """Importing ``reflex_django.auth.state`` must not build ``DjangoAuthState`` yet."""
    import reflex_django.auth.state as auth_state_module

    assert "DjangoAuthState" not in auth_state_module.__dict__


def test_build_django_auth_state_bootstraps_django() -> None:
    from reflex_django.auth.state_builders import build_django_auth_state

    cls = build_django_auth_state()
    assert cls.__name__ == "DjangoAuthState"
    assert hasattr(cls, "submit_login_form")
