"""ASGI entry point for the Django-outer, single-port architecture.

Use this as the WSGI/ASGI ``application`` in production:

.. code-block:: python

    # config/asgi.py
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    from reflex_django.asgi_entry import application  # noqa: F401

then run with any ASGI server:

.. code-block:: bash

    uvicorn config.asgi:application --host 0.0.0.0 --port 8000

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER` (the new
default), Django owns the outer ASGI app, lifespan is forwarded to Reflex,
and the Socket.IO/upload/health endpoints are mounted as ASGI sub-apps
under Django via :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`.
In legacy ``reflex_led`` or ``django_led`` modes, this entry point falls
back to building the Reflex-outer stack with the same Django dispatcher
that :mod:`reflex_django.asgi` provided before.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from reflex_django.asgi import ASGIApp, django_asgi_application
from reflex_django.django_outer_dispatcher import (
    DEFAULT_RESERVED_REFLEX_PREFIXES,
    DjangoOuterDispatcher,
)
from reflex_django.routing import UrlRoutingMode, resolve_url_routing

if TYPE_CHECKING:
    from reflex.app import App


_REFLEX_FRONTEND_MOUNT_ENV = "REFLEX_MOUNT_FRONTEND_COMPILED_APP"


def _unwrap_reflex_inner_asgi(rx_app: App) -> ASGIApp:
    """Return Reflex's inner ASGI app (Starlette with Socket.IO etc.) for mounting.

    Reflex normally wraps ``app._api`` in :meth:`reflex.app.App._context_middleware`
    and a top-level Starlette that owns lifespan. In ``DJANGO_OUTER`` mode we
    own lifespan ourselves (see
    :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`), so
    we only need the inner Starlette wrapped in the context middleware.

    Args:
        rx_app: The configured :class:`reflex.app.App` instance.

    Returns:
        An ASGI callable that handles Socket.IO/upload/health requests.

    Raises:
        RuntimeError: If Reflex's private ``_api`` attribute is missing
            (likely a Reflex upgrade incompatibility).
    """
    inner = getattr(rx_app, "_api", None)
    if inner is None:
        msg = (
            "Reflex app has no `_api` attribute. "
            "reflex_django is built against Reflex's private ASGI layout; "
            "pin a compatible Reflex version or report this incompatibility."
        )
        raise RuntimeError(msg)

    context_middleware = getattr(rx_app, "_context_middleware", None)
    if not callable(context_middleware):
        return inner
    return context_middleware(inner)


def _lifespan_cm_for_app(rx_app: App) -> Callable[..., Any] | None:
    """Return the lifespan asynccontextmanager bound to ``rx_app``."""
    fn = getattr(rx_app, "_run_lifespan_tasks", None)
    if not callable(fn):
        return None
    return fn


def _disable_reflex_frontend_mount() -> None:
    """Stop Reflex from appending its catch-all ``StaticFiles`` mount to ``_api``.

    Django serves the SPA in ``DJANGO_OUTER`` mode (either via staticfiles
    or :class:`~reflex_django.views.mount.ReflexMountView` reverse-proxying
    Vite). Letting Reflex mount its own catch-all on ``_api`` would shadow
    Django's URL space if anything routed to Reflex by mistake.
    """
    import os

    if _REFLEX_FRONTEND_MOUNT_ENV not in os.environ:
        os.environ[_REFLEX_FRONTEND_MOUNT_ENV] = "0"


def _build_reflex_outer_application() -> ASGIApp:
    """Legacy path: keep the Reflex-outer dispatcher for opt-out users."""
    from reflex_django.app_factory import ensure_django_led_app_ready

    rx_app = ensure_django_led_app_ready()
    return rx_app()


def build_django_outer_application() -> ASGIApp:
    """Compose Django-outer ASGI app for single-port deployment.

    Steps:

    1. Run the standard integration bootstrap (Django settings, get_config
       patch, Reflex CLI layout, page imports).
    2. Build the Reflex app via the existing factory; the plugin's
       ``post_compile`` runs but skips :attr:`reflex.app.App.api_transformer`
       wiring in ``DJANGO_OUTER`` mode (see
       :meth:`reflex_django.plugin.ReflexDjangoPlugin._configure`).
    3. Disable Reflex's frontend catch-all so Django owns ``/``.
    4. Extract Reflex's inner Starlette (``_api``) wrapped with its
       per-request context middleware.
    5. Build Django's ASGI app (with staticfiles).
    6. Wrap both in :class:`DjangoOuterDispatcher` so Django gets every
       request that does not match a Reflex reserved path.

    Returns:
        The composed ASGI application.
    """
    _disable_reflex_frontend_mount()

    from reflex_django.app_factory import ensure_django_led_app_ready
    from reflex_django.integration import install_reflex_django_integration

    install_reflex_django_integration()
    rx_app = ensure_django_led_app_ready()

    reflex_inner = _unwrap_reflex_inner_asgi(rx_app)
    lifespan_cm = _lifespan_cm_for_app(rx_app)
    django_asgi = django_asgi_application()

    reserved = _reserved_prefixes_for_dispatcher()

    return DjangoOuterDispatcher(
        django=django_asgi,
        reflex=reflex_inner,
        lifespan_cm=lifespan_cm,
        reserved_prefixes=reserved,
    )


def _reserved_prefixes_for_dispatcher() -> tuple[str, ...]:
    """Combine the built-in Reflex prefixes with any user additions.

    ``settings.REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES`` may add custom
    Reflex-owned paths (advanced; rarely needed).
    """
    extra: tuple[str, ...] = ()
    try:
        from django.conf import settings

        raw = getattr(settings, "REFLEX_DJANGO_RESERVED_REFLEX_PREFIXES", ())
        if raw:
            extra = tuple(str(p) for p in raw if str(p).strip())
    except Exception:
        pass
    return (*DEFAULT_RESERVED_REFLEX_PREFIXES, *extra)


def build_application() -> ASGIApp:
    """Build the ASGI application appropriate for the configured routing mode."""
    mode = resolve_url_routing()
    if mode == UrlRoutingMode.DJANGO_OUTER:
        return build_django_outer_application()
    return _build_reflex_outer_application()


# Module-level ``application`` is lazily constructed on first access so that
# bare ``import reflex_django.asgi_entry`` does not import Django/Reflex
# unnecessarily (for example during ``manage.py`` argument parsing).
_application: ASGIApp | None = None


def _ensure_application() -> ASGIApp:
    global _application
    if _application is None:
        _application = build_application()
    return _application


async def application(scope: Any, receive: Any, send: Any) -> Any:
    """ASGI 3 callable suitable for ``uvicorn``/``daphne``/``granian``.

    Declared ``async def`` so ASGI servers like uvicorn detect it as ASGI 3
    via :func:`asyncio.iscoroutinefunction` — a plain ``def`` is treated as
    ASGI 2 (``app(scope) -> instance``) and would break on the three-arg
    signature.

    Delegates to a lazily-constructed dispatcher so importing this module
    is side-effect free until the first request.
    """
    await _ensure_application()(scope, receive, send)


__all__ = [
    "application",
    "build_application",
    "build_django_outer_application",
]
