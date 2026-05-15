"""Auth decorators for Reflex pages and event handlers."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

import reflex as rx

from reflex_django.context import current_user

F = TypeVar("F", bound=Callable[..., Any])


def _resolve_login_url(login_url: str | None) -> str:
    from django.conf import settings

    if login_url is not None:
        return login_url
    return str(getattr(settings, "REFLEX_DJANGO_LOGIN_URL", "/login"))


def _is_state_handler(fn: Callable[..., Any]) -> bool:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    return bool(params) and params[0].name == "self"


def _wrap_page(
    page: Callable[..., rx.Component],
    login_url: str | None,
) -> Callable[..., rx.Component]:
    del login_url

    from reflex_django.auth.state import DjangoAuthState

    def protected_page() -> rx.Component:
        return rx.fragment(
            rx.cond(
                DjangoAuthState.is_hydrated & DjangoAuthState.is_authenticated,  # type: ignore[operator]
                page(),
                rx.center(
                    rx.text(
                        "Loading...",
                        on_mount=DjangoAuthState.redirect_to_login,
                    ),
                ),
            ),
        )

    protected_page.__name__ = getattr(page, "__name__", "protected_page")
    protected_page.__qualname__ = getattr(page, "__qualname__", protected_page.__name__)
    return protected_page


def _wrap_event(fn: F, login_url: str | None) -> F:
    resolved = _resolve_login_url(login_url)

    @functools.wraps(fn)
    async def async_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved)
        return await fn(state, *args, **kwargs)

    @functools.wraps(fn)
    def sync_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved)
        return fn(state, *args, **kwargs)

    if inspect.iscoroutinefunction(fn):
        return async_wrapper  # type: ignore[return-value]
    return sync_wrapper  # type: ignore[return-value]


def login_required(
    function: Callable[..., Any] | None = None,
    *,
    login_url: str | None = None,
) -> Any:
    """Require login for a Reflex page or state event handler.

    Pages (no ``self`` parameter) get a UI redirect via :class:`DjangoAuthState`.
    Event handlers (first parameter ``self``) check the Django session and return
    ``rx.redirect`` when anonymous.

    For data access inside handlers, also use
    :func:`reflex_django.auth.shortcuts.require_login_user`.

    Args:
        function: Page or handler when used as ``@login_required`` without parens.
        login_url: Optional login path (defaults to ``REFLEX_DJANGO_LOGIN_URL``).

    Returns:
        Decorator or wrapped callable.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_event(fn, login_url)
        return _wrap_page(fn, login_url)

    if function is not None:
        return decorator(function)
    return decorator


__all__ = ["login_required"]
