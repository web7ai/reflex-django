"""Auth decorators for Reflex pages and event handlers."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

import reflex as rx

from reflex_django.auth.shortcuts import auser_has_perm
from reflex_django.bridge.context import current_user

F = TypeVar("F", bound=Callable[..., Any])


def _resolve_login_url(login_url: str | None) -> str:
    from django.conf import settings

    if login_url is not None:
        return login_url
    return str(getattr(settings, "RX_LOGIN_URL", "/login"))


def _is_state_handler(fn: Callable[..., Any]) -> bool:
    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    return bool(params) and params[0].name == "self"


def _auth_state_for_pages() -> type:
    """State class whose snapshot vars gate page-level decorators."""
    from reflex_django.auth.state import DjangoAuthState

    return DjangoAuthState


def _wrap_page(
    page: Callable[..., rx.Component],
    login_url: str | None,
) -> Callable[..., rx.Component]:
    del login_url
    auth_state = _auth_state_for_pages()

    def protected_page() -> rx.Component:
        return rx.fragment(
            rx.cond(
                auth_state.is_hydrated & auth_state.is_authenticated,  # type: ignore[operator]
                page(),
                rx.center(
                    rx.text(
                        "Loading...",
                        on_mount=auth_state.redirect_to_login,
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

    Pages (no ``self`` parameter) get a UI redirect via :class:`DjangoAuthState`
    snapshot vars. Event handlers (first parameter ``self``) check the Django
    session and return ``rx.redirect`` when anonymous.

    For data access inside handlers, also use
    :func:`reflex_django.auth.shortcuts.require_login_user`.

    Args:
        function: Page or handler when used as ``@login_required`` without parens.
        login_url: Optional login path (defaults to ``RX_LOGIN_URL``).

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


def _wrap_permission_page(
    page: Callable[..., rx.Component],
    perm: str,
    *,
    fallback: Callable[..., rx.Component] | None,
    redirect: str | None,
    login_url: str | None,
) -> Callable[..., rx.Component]:
    """Page wrapper: login gate in UI; enforce ``perm`` on event handlers."""
    del perm, redirect, login_url
    auth_state = _auth_state_for_pages()

    def protected_page() -> rx.Component:
        if fallback is not None:
            return rx.fragment(
                rx.cond(
                    auth_state.is_hydrated & auth_state.is_authenticated,  # type: ignore[operator]
                    page(),
                    fallback(),
                ),
            )
        return rx.fragment(
            rx.cond(
                auth_state.is_hydrated & auth_state.is_authenticated,  # type: ignore[operator]
                page(),
                rx.center(
                    rx.text(
                        "Loading...",
                        on_mount=auth_state.redirect_to_login,
                    ),
                ),
            ),
        )

    protected_page.__name__ = getattr(page, "__name__", "protected_page")
    protected_page.__qualname__ = getattr(page, "__qualname__", protected_page.__name__)
    return protected_page


def _wrap_permission_event(
    fn: F,
    perm: str,
    *,
    redirect: str | None,
    login_url: str | None,
    on_denied: Callable[..., Any] | None,
) -> F:
    resolved = redirect or _resolve_login_url(login_url)

    @functools.wraps(fn)
    async def async_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved)
        if not await auser_has_perm(user, perm):
            if on_denied is not None:
                result = on_denied(state)
                if inspect.isawaitable(result):
                    return await result
                return result
            if hasattr(state, "on_permission_denied"):
                return await state.on_permission_denied()
            return rx.redirect(resolved)
        return await fn(state, *args, **kwargs)

    @functools.wraps(fn)
    def sync_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved)
        msg = "permission_required does not support sync handlers with permission checks"
        raise RuntimeError(msg)

    if inspect.iscoroutinefunction(fn):
        return async_wrapper  # type: ignore[return-value]
    return sync_wrapper  # type: ignore[return-value]


def permission_required(
    perm: str,
    function: Callable[..., Any] | None = None,
    *,
    login_url: str | None = None,
    redirect: str | None = None,
    fallback: Callable[..., rx.Component] | None = None,
    on_denied: Callable[..., Any] | None = None,
) -> Any:
    """Require a Django permission for a Reflex page or event handler.

    Event handlers check :func:`current_user` and
    :func:`~reflex_django.auth.shortcuts.auser_has_perm`. On denial, call
    ``on_denied(state)`` if provided, else ``state.on_permission_denied()`` when
    present, else ``rx.redirect``.

    Args:
        perm: Permission string (``app_label.codename``).
        function: Page or handler when used as ``@permission_required("perm")``.
        login_url: Redirect target when anonymous (defaults to settings).
        redirect: Redirect target when permission denied (defaults to login_url).
        fallback: Optional component factory for denied page access.
        on_denied: Optional callback for denied event handlers.

    Returns:
        Decorator or wrapped callable.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_permission_event(
                fn,
                perm,
                redirect=redirect,
                login_url=login_url,
                on_denied=on_denied,
            )
        return _wrap_permission_page(
            fn,
            perm,
            fallback=fallback,
            redirect=redirect,
            login_url=login_url,
        )

    if function is not None:
        return decorator(function)
    return decorator


__all__ = ["login_required", "permission_required"]
