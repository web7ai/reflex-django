"""Canonical :class:`DjangoAuthState` for canned auth pages."""

from __future__ import annotations

from reflex_django.auth.state_builders import get_or_create_django_auth_state

DjangoAuthState = get_or_create_django_auth_state()

__all__ = ["DjangoAuthState"]
