"""Canonical :class:`DjangoAuthState` for canned auth pages."""

from __future__ import annotations

from typing import Any

__all__ = ["DjangoAuthState"]


def __getattr__(name: str) -> Any:
    if name == "DjangoAuthState":
        from reflex_django.auth.state_builders import get_or_create_django_auth_state

        cls = get_or_create_django_auth_state()
        globals()[name] = cls
        return cls
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
