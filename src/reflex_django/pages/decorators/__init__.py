"""Decorators that register Reflex pages for Django-led projects."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

PAGE_REGISTRY: list[PageRegistration] = []


@dataclass
class PageRegistration:
    """Metadata for a page registered via :func:`page`."""

    render_fn: Callable[..., Any]
    route: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)
    breadcrumbs: tuple[tuple[str, str | None], ...] = ()


def get_breadcrumbs_for_route(route: str | None) -> tuple[tuple[str, str | None], ...]:
    """Return breadcrumb segments registered for *route*."""
    if not route:
        return ()
    for registration in PAGE_REGISTRY:
        if registration.route == route:
            return registration.breadcrumbs
    return ()


def page(
    route: str | None = None,
    *,
    login_required: bool = False,
    login_url: str | None = None,
    breadcrumbs: Sequence[tuple[str, str | None]] | None = None,
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a Reflex page and record it in :data:`PAGE_REGISTRY`.

    Wraps :func:`reflex.page` so pages are discoverable from Django settings.

    Args:
        route: Reflex client route (e.g. ``"/"``, ``"/about"``).
        login_required: When ``True``, anonymous visitors are redirected to login.
        login_url: Optional login path override for :paramref:`login_required`.
        breadcrumbs: Optional ``(label, href)`` pairs; ``href=None`` for active segment.
        **kwargs: Forwarded to :func:`reflex.page` (``title``, ``on_load``, …).

    Returns:
        The decorator.
    """
    import reflex as rx

    breadcrumb_tuple = tuple(breadcrumbs or ())

    def decorator(render_fn: Callable[..., Any]) -> Callable[..., Any]:
        from reflex_django.app_factory import migrate_decorated_pages_app_name
        from reflex_django.mount_config import ensure_mount_config_loaded, resolve_app_name

        page_kwargs = dict(kwargs)
        if route is not None:
            page_kwargs["route"] = route

        protected_fn = render_fn
        if login_required:
            from reflex_django.auth.decorators import login_required as require_login

            protected_fn = require_login(login_url=login_url)(render_fn)

        if route is None or not any(
            reg.route == route for reg in PAGE_REGISTRY
        ):
            PAGE_REGISTRY.append(
                PageRegistration(
                    render_fn=protected_fn,
                    route=route,
                    kwargs=page_kwargs,
                    breadcrumbs=breadcrumb_tuple,
                )
            )
        ensure_mount_config_loaded()
        wrapped = rx.page(**page_kwargs)(protected_fn)
        migrate_decorated_pages_app_name(resolve_app_name())
        return wrapped

    return decorator


# Backward compatibility (removed in a future release).
reflex_page = page


def reflex_template(
    template_fn: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap a page render function with a layout template callable.

    Example::

        @reflex_template(template)
        @page(route="/")
        def index():
            return rx.text("Hello")

    Args:
        template_fn: A callable ``template(route=..., ...)`` that returns a
            decorator (same pattern as project layout helpers).

    Returns:
        A decorator that applies *template_fn* then registers the page.
    """

    def decorator(render_fn: Callable[..., Any]) -> Callable[..., Any]:
        return template_fn()(render_fn)

    return decorator


def clear_page_registry() -> None:
    """Clear :data:`PAGE_REGISTRY` (tests only)."""
    PAGE_REGISTRY.clear()


__all__ = [
    "PAGE_REGISTRY",
    "PageRegistration",
    "clear_page_registry",
    "get_breadcrumbs_for_route",
    "page",
    "reflex_page",
    "reflex_template",
]
