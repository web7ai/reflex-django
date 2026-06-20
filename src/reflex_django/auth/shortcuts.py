"""Imperative auth helpers for Reflex event handlers (Django sessions)."""

from __future__ import annotations

from typing import Any

from asgiref.sync import sync_to_async

from reflex_django.bridge.context import current_user


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


async def auser_in_group(user: Any, group: str) -> bool:
    """Return whether *user* belongs to the Django group named *group*.

    Args:
        user: Django user instance.
        group: Group name.

    Returns:
        Whether the user is a member of the group (superusers always pass).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    groups = getattr(user, "groups", None)
    if groups is None:
        return False

    def _check() -> bool:
        return groups.filter(name=group).exists()

    return await sync_to_async(_check)()


__all__ = [
    "ReflexDjangoAuthError",
    "auser_has_perm",
    "auser_in_group",
    "require_login_user",
]
