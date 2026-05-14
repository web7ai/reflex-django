"""Server-side auth helpers for Reflex event handlers (Django sessions)."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from asgiref.sync import sync_to_async

from reflex_django.context import current_user

F = TypeVar("F", bound=Callable[..., Any])


class ReflexDjangoAuthError(PermissionError):
    """Raised when an operation requires a logged-in Django user."""


def _login_url(explicit: str | None) -> str:
    from django.conf import settings

    if explicit is not None:
        return explicit
    return str(getattr(settings, "REFLEX_DJANGO_LOGIN_URL", "/login"))


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


def django_login_required(
    redirect_to: str | None = None,
) -> Callable[[F], F]:
    """Decorator for Reflex event handlers that require a logged-in user.

    Anonymous users receive ``rx.redirect(...)`` to the login URL (from the
    decorator argument or ``settings.REFLEX_DJANGO_LOGIN_URL``).

    Args:
        redirect_to: Optional path to redirect to (e.g. ``"/login"``).

    Returns:
        Decorator that wraps async (or sync) handler methods on :class:`reflex.state.State`.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def async_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
            import reflex as rx

            user = current_user()
            if not getattr(user, "is_authenticated", False):
                return rx.redirect(_login_url(redirect_to))
            return await fn(state, *args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
            import reflex as rx

            user = current_user()
            if not getattr(user, "is_authenticated", False):
                return rx.redirect(_login_url(redirect_to))
            return fn(state, *args, **kwargs)

        if inspect.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "ReflexDjangoAuthError",
    "auser_has_perm",
    "django_login_required",
    "require_login_user",
]
