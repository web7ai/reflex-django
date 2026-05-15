"""Imperative auth helpers for Reflex event handlers (Django sessions)."""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async

from reflex_django.context import current_user


class ReflexDjangoAuthError(PermissionError):
    """Raised when an operation requires a logged-in Django user."""


def require_login_user() -> Any:
    """Return ``request.user`` for the active event or raise.

    Returns:
        The authenticated Django user.

    Raises:
        ReflexDjangoAuthError: When the user is anonymous or no request is bound.
    """
    user = current_user()
    if not getattr(user, "is_authenticated", False):
        msg = "This action requires an authenticated user."
        raise ReflexDjangoAuthError(msg)
    return user


async def auser_has_perm(user: Any, perm: str) -> bool:
    """Async wrapper for :meth:`django.contrib.auth.models.AbstractUser.has_perm`.

    Args:
        user: Django user instance.
        perm: Permission string in ``app_label.codename`` form.

    Returns:
        Whether the user has the permission.
    """
    return await sync_to_async(user.has_perm)(perm)


__all__ = [
    "ReflexDjangoAuthError",
    "auser_has_perm",
    "require_login_user",
]
