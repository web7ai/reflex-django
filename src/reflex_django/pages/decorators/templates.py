"""Built-in page layout decorator for Django-first projects."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import reflex as rx

from reflex_django.pages.decorators import get_breadcrumbs_for_route, page

_DEFAULT_META = [
    {
        "name": "viewport",
        "content": "width=device-width, shrink-to-fit=no, initial-scale=1",
    },
]


def centered_template(
    route: str,
    *,
    title: str | None = None,
    description: str | None = None,
    on_load: Any = None,
    meta: list[dict[str, str]] | None = None,
    show_title: bool = True,
    **page_kwargs: Any,
) -> Callable[[Callable[[], rx.Component]], Callable[[], rx.Component]]:
    """Register a Reflex page with a minimal centered layout.

    Use in Django app ``views.py`` (import the module from ``urls.py`` so decorators
    run at startup). This is **not** a Django ``HttpResponse`` view.

    Example::

        from reflex_django.pages.decorators.templates import centered_template as template
        from reflex_django.states import AppState
        import reflex as rx

        class HomeState(AppState):
            @rx.event
            async def on_load(self):
                ...

        @template(route="/", title="Home", on_load=HomeState.on_load)
        def index() -> rx.Component:
            return rx.text("Hello")

    Args:
        route: Client-side route (e.g. ``"/"``, ``"/about"``).
        title: Browser tab title and optional in-page heading.
        description: Page description meta tag.
        on_load: Reflex ``on_load`` handler(s).
        meta: Extra meta tag dicts.
        show_title: When ``True`` and *title* is set, render an ``rx.heading``.
        **page_kwargs: Forwarded to :func:`reflex.page` (via :func:`~reflex_django.pages.decorators.page`).

    Returns:
        A decorator for the page render function.
    """
    all_meta = [*_DEFAULT_META, *(meta or [])]
    load_handlers = (
        None
        if on_load is None
        else (on_load if isinstance(on_load, list) else [on_load])
    )

    def decorator(page_content: Callable[[], rx.Component]) -> Callable[[], rx.Component]:
        @page(
            route=route,
            title=title,
            description=description,
            on_load=load_handlers,
            meta=all_meta,
            **page_kwargs,
        )
        def wrapped_page() -> rx.Component:
            body = page_content()
            children: list[rx.Component] = []
            if show_title and title:
                children.append(
                    rx.heading(title, size="8", margin_bottom="1rem", width="100%")
                )
            children.append(body)
            return rx.container(
                rx.vstack(*children, spacing="4", width="100%"),
                max_width="48rem",
                margin="auto",
                padding="2rem",
                width="100%",
            )

        return wrapped_page

    return decorator


def render_breadcrumb_trail(
    *segments: tuple[str, str | None],
    home_label: str = "Home",
    home_href: str = "/",
) -> rx.Component:
    """Build a breadcrumb trail from ``(label, href)`` pairs."""
    parts: list[rx.Component] = [
        rx.link(home_label, href=home_href, class_name="breadcrumb-link"),
    ]
    for label, href in segments:
        parts.append(rx.text("/", color="var(--gray-8)", size="1"))
        if href:
            parts.append(rx.link(label, href=href, class_name="breadcrumb-link"))
        else:
            parts.append(rx.text(label, class_name="breadcrumb-active"))
    return rx.hstack(*parts, spacing="2", align="center", margin_bottom="0.8em")


def render_breadcrumbs_for_current_route(
    *,
    home_label: str = "Home",
    home_href: str = "/",
) -> rx.Component:
    """Render breadcrumbs for the active route from :data:`PAGE_REGISTRY` metadata."""
    from reflex_django.pages.decorators import PAGE_REGISTRY

    path = rx.State.router.page.path
    match_args: list = [path]
    seen: set[str | None] = set()
    for registration in PAGE_REGISTRY:
        route = registration.route
        crumbs = registration.breadcrumbs
        if not route or not crumbs or route in seen:
            continue
        seen.add(route)
        match_args.append(
            (
                route,
                render_breadcrumb_trail(
                    *crumbs,
                    home_label=home_label,
                    home_href=home_href,
                ),
            )
        )
    match_args.append(rx.fragment())
    return rx.match(*match_args)


def layout_template(
    route: str,
    *,
    title: str | None = None,
    description: str | None = None,
    on_load: Any = None,
    meta: list[dict[str, str]] | None = None,
    breadcrumbs: Sequence[tuple[str, str | None]] | None = None,
    login_required: bool = False,
    login_url: str | None = None,
    shell: Callable[[rx.Component], rx.Component] | None = None,
    **page_kwargs: Any,
) -> Callable[[Callable[[], rx.Component]], Callable[[], rx.Component]]:
    """Register a page with optional shell wrapper and breadcrumb metadata.

    Use *shell* to inject app chrome (sidebar, navbar). Breadcrumbs are stored on
    :data:`~reflex_django.pages.decorators.PAGE_REGISTRY` and can be rendered via
    :func:`render_breadcrumbs_for_current_route`.
    """
    all_meta = [*_DEFAULT_META, *(meta or [])]
    load_handlers = (
        None
        if on_load is None
        else (on_load if isinstance(on_load, list) else [on_load])
    )

    def decorator(page_content: Callable[[], rx.Component]) -> Callable[[], rx.Component]:
        @page(
            route=route,
            title=title,
            description=description,
            on_load=load_handlers,
            meta=all_meta,
            breadcrumbs=breadcrumbs,
            login_required=login_required,
            login_url=login_url,
            **page_kwargs,
        )
        def wrapped_page() -> rx.Component:
            body = page_content()
            if shell is not None:
                return shell(body)
            return body

        return wrapped_page

    return decorator


__all__ = [
    "centered_template",
    "layout_template",
    "render_breadcrumb_trail",
    "render_breadcrumbs_for_current_route",
]
