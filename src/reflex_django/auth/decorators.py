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
    if login_url is not None:
        return login_url
    from reflex_django.auth.settings import get_auth_settings

    return get_auth_settings().login_url


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
        login_url: Optional login path (defaults to ``RX_AUTH["LOGIN_URL"]``).

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


def _guarded_page(
    page: Callable[..., rx.Component],
    *,
    guard_spec: Any,
    visible_cond: Any,
    fallback: Callable[..., rx.Component] | None,
) -> Callable[..., rx.Component]:
    """Render *page* behind a UI gate plus an authoritative server-side guard.

    ``guard_spec`` is attached to an always-mounted (hidden) element so it runs
    on every visit regardless of the ``visible_cond`` snapshot. This is the
    security boundary: an authenticated user who lacks the required
    permission/role is redirected by the server even though the snapshot vars
    used for ``visible_cond`` are client-visible.
    """
    auth_state = _auth_state_for_pages()

    def protected_page() -> rx.Component:
        denied = (
            fallback() if fallback is not None else rx.center(rx.text("Loading..."))
        )
        return rx.fragment(
            rx.box(on_mount=guard_spec, display="none"),
            rx.cond(visible_cond, page(), denied),
        )

    protected_page.__name__ = getattr(page, "__name__", "protected_page")
    protected_page.__qualname__ = getattr(page, "__qualname__", protected_page.__name__)
    return protected_page


def _wrap_permission_page(
    page: Callable[..., rx.Component],
    perm: str,
    *,
    fallback: Callable[..., rx.Component] | None,
    redirect: str | None,
    login_url: str | None,
) -> Callable[..., rx.Component]:
    """Page wrapper that enforces ``perm`` server-side on mount."""
    del login_url
    auth_state = _auth_state_for_pages()
    return _guarded_page(
        page,
        guard_spec=auth_state.require_permission(perm, redirect or ""),  # type: ignore[attr-defined]
        # No client-visible permission snapshot exists, so gate the UI on auth
        # and rely on the server guard to redirect unauthorized users.
        visible_cond=auth_state.is_hydrated & auth_state.is_authenticated,  # type: ignore[operator]
        fallback=fallback,
    )


def _wrap_role_page(
    page: Callable[..., rx.Component],
    *,
    guard_spec: Any,
    visible_cond: Any,
    fallback: Callable[..., rx.Component] | None,
) -> Callable[..., rx.Component]:
    return _guarded_page(
        page,
        guard_spec=guard_spec,
        visible_cond=visible_cond,
        fallback=fallback,
    )


def _wrap_check_event(
    fn: F,
    *,
    check: Callable[[Any], Any],
    resolved_redirect: str,
    on_denied: Callable[..., Any] | None,
    sync_supported: bool,
    sync_label: str,
) -> F:
    """Wrap an event handler so it runs only when ``check(user)`` passes.

    ``check`` may be sync or async and receives the Django user. On denial,
    calls ``on_denied(state)`` if given, else ``state.on_permission_denied()``
    when present, else redirects to ``resolved_redirect``.
    """

    async def _denied(state: Any) -> Any:
        if on_denied is not None:
            result = on_denied(state)
            if inspect.isawaitable(result):
                return await result
            return result
        if hasattr(state, "on_permission_denied"):
            return await state.on_permission_denied()
        return rx.redirect(resolved_redirect)

    @functools.wraps(fn)
    async def async_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved_redirect)
        result = check(user)
        allowed = await result if inspect.isawaitable(result) else result
        if not allowed:
            return await _denied(state)
        return await fn(state, *args, **kwargs)

    @functools.wraps(fn)
    def sync_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not getattr(user, "is_authenticated", False):
            return rx.redirect(resolved_redirect)
        if not sync_supported:
            msg = (
                f"{sync_label} does not support sync handlers with this check; "
                "make the handler async."
            )
            raise RuntimeError(msg)
        if not check(user):
            if on_denied is not None:
                return on_denied(state)
            return rx.redirect(resolved_redirect)
        return fn(state, *args, **kwargs)

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

    Pages enforce ``perm`` on the server via an always-mounted guard
    (:meth:`DjangoAuthState.require_permission`): an authenticated user who
    lacks the permission is redirected to ``redirect`` (or the login URL), not
    just hidden in the UI. Event handlers check :func:`current_user` and
    :func:`~reflex_django.auth.shortcuts.auser_has_perm`.

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
    resolved_redirect = redirect or _resolve_login_url(login_url)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_check_event(
                fn,
                check=lambda user: auser_has_perm(user, perm),
                resolved_redirect=resolved_redirect,
                on_denied=on_denied,
                sync_supported=False,
                sync_label="permission_required",
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


def group_required(
    group: str,
    function: Callable[..., Any] | None = None,
    *,
    login_url: str | None = None,
    redirect: str | None = None,
    fallback: Callable[..., rx.Component] | None = None,
    on_denied: Callable[..., Any] | None = None,
) -> Any:
    """Require Django group membership for a Reflex page or event handler.

    Superusers always pass. Pages enforce membership server-side on mount;
    handlers check :func:`~reflex_django.auth.shortcuts.auser_in_group`.

    Args:
        group: Django group name.
        function: Page or handler when used as ``@group_required("Editors")``.
        login_url: Redirect target when anonymous (defaults to settings).
        redirect: Redirect target when denied (defaults to login_url).
        fallback: Optional component factory for denied page access.
        on_denied: Optional callback for denied event handlers.
    """
    from reflex_django.auth.shortcuts import auser_in_group

    resolved_redirect = redirect or _resolve_login_url(login_url)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_check_event(
                fn,
                check=lambda user: auser_in_group(user, group),
                resolved_redirect=resolved_redirect,
                on_denied=on_denied,
                sync_supported=False,
                sync_label="group_required",
            )
        auth_state = _auth_state_for_pages()
        return _wrap_role_page(
            fn,
            guard_spec=auth_state.require_group(group, redirect or ""),  # type: ignore[attr-defined]
            visible_cond=(
                auth_state.is_hydrated  # type: ignore[operator]
                & auth_state.is_authenticated
                & auth_state.group_names.contains(group)
            ),
            fallback=fallback,
        )

    if function is not None:
        return decorator(function)
    return decorator


def staff_required(
    function: Callable[..., Any] | None = None,
    *,
    login_url: str | None = None,
    redirect: str | None = None,
    fallback: Callable[..., rx.Component] | None = None,
    on_denied: Callable[..., Any] | None = None,
) -> Any:
    """Require ``user.is_staff`` for a Reflex page or event handler."""
    resolved_redirect = redirect or _resolve_login_url(login_url)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_check_event(
                fn,
                check=lambda user: bool(getattr(user, "is_staff", False)),
                resolved_redirect=resolved_redirect,
                on_denied=on_denied,
                sync_supported=True,
                sync_label="staff_required",
            )
        auth_state = _auth_state_for_pages()
        return _wrap_role_page(
            fn,
            guard_spec=auth_state.require_staff(redirect or ""),  # type: ignore[attr-defined]
            visible_cond=(
                auth_state.is_hydrated  # type: ignore[operator]
                & auth_state.is_authenticated
                & auth_state.is_staff
            ),
            fallback=fallback,
        )

    if function is not None:
        return decorator(function)
    return decorator


def superuser_required(
    function: Callable[..., Any] | None = None,
    *,
    login_url: str | None = None,
    redirect: str | None = None,
    fallback: Callable[..., rx.Component] | None = None,
    on_denied: Callable[..., Any] | None = None,
) -> Any:
    """Require ``user.is_superuser`` for a Reflex page or event handler."""
    resolved_redirect = redirect or _resolve_login_url(login_url)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _is_state_handler(fn):
            return _wrap_check_event(
                fn,
                check=lambda user: bool(getattr(user, "is_superuser", False)),
                resolved_redirect=resolved_redirect,
                on_denied=on_denied,
                sync_supported=True,
                sync_label="superuser_required",
            )
        auth_state = _auth_state_for_pages()
        return _wrap_role_page(
            fn,
            guard_spec=auth_state.require_superuser(redirect or ""),  # type: ignore[attr-defined]
            visible_cond=(
                auth_state.is_hydrated  # type: ignore[operator]
                & auth_state.is_authenticated
                & auth_state.is_superuser
            ),
            fallback=fallback,
        )

    if function is not None:
        return decorator(function)
    return decorator


__all__ = [
    "group_required",
    "login_required",
    "permission_required",
    "staff_required",
    "superuser_required",
]
