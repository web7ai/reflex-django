"""Optional decorators that register Reflex pages for Django-led projects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

PAGE_REGISTRY: list[PageRegistration] = []


@dataclass
class PageRegistration:
    """Metadata for a page registered via :func:`reflex_page`."""

    render_fn: Callable[..., Any]
    route: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


def reflex_page(
    route: str | None = None,
    **kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a Reflex page and record it in :data:`PAGE_REGISTRY`.

    Wraps :func:`reflex.page` so pages are discoverable from Django settings.

    Args:
        route: Reflex client route (e.g. ``"/"``, ``"/about"``).
        **kwargs: Forwarded to :func:`reflex.page` (``title``, ``on_load``, …).

    Returns:
        The decorator.
    """
    import reflex as rx

    def decorator(render_fn: Callable[..., Any]) -> Callable[..., Any]:
        page_kwargs = dict(kwargs)
        if route is not None:
            page_kwargs["route"] = route
        PAGE_REGISTRY.append(
            PageRegistration(
                render_fn=render_fn,
                route=route,
                kwargs=page_kwargs,
            )
        )
        return rx.page(**page_kwargs)(render_fn)

    return decorator


def reflex_template(
    template_fn: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap a page render function with a layout template callable.

    Example::

        @reflex_template(template)
        @reflex_page(route="/")
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
