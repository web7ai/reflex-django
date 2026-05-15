"""Page-level auth decorators (UI redirect only)."""

from __future__ import annotations

from collections.abc import Callable

import reflex as rx

from reflex_django.auth.state import DjangoAuthState


def login_required(page: Callable[..., rx.Component]) -> Callable[..., rx.Component]:
    """Require authentication before rendering a page (redirects to login).

    This only affects what the user sees in the browser. Protect private data
    in event handlers with :func:`reflex_django.django_login_required` or
    :func:`reflex_django.require_login_user`.

    Args:
        page: A page component callable (``@rx.page`` target).

    Returns:
        Wrapped page that shows a loading state and redirects when anonymous.
    """

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


__all__ = ["login_required"]
