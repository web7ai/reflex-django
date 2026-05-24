"""ASGI composition for reflex-django.

Exposes two helpers:

- :func:`build_django_asgi` returns the Django ASGI callable, ensuring
  :func:`reflex_django.conf.configure_django` has run first.
- :func:`make_dispatcher` returns a transformer suitable for assigning to
  :attr:`reflex.app.App.api_transformer`. The transformer wraps Reflex's
  Starlette app with a path-prefix dispatcher that forwards backend routes to
  Django and everything else (including Socket.IO ``/_event``, ``/_upload``,
  ``/_health``, and the compiled frontend mount) to Reflex.

The dispatcher only inspects ``scope["type"]`` and ``scope["path"]``. ASGI
lifespan events are always forwarded to Reflex's inner app, because Reflex owns
the lifespan handler via :meth:`reflex.app_mixins.LifespanMixin._run_lifespan_tasks`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from reflex_django.conf import configure_django
from reflex_django.routing import UrlRoutingMode

ASGIScope = MutableMapping[str, Any]
ASGIMessage = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]


# Path prefixes Reflex reserves for its own endpoints. The plugin uses this set
# to reject a backend prefix that would shadow Reflex internals.
RESERVED_REFLEX_PREFIXES: tuple[str, ...] = (
    "/_event",
    "/_upload",
    "/_health",
    "/_all_routes",
    "/ping",
    "/auth-codespace",
)


def bootstrap_django_led_runtime() -> None:
    """Load Reflex config, pages, and app factory for django_led mode (idempotent).

    Called from :func:`build_django_asgi` so Django settings supply Reflex config
    (no ``rxconfig.py`` on disk) and ``@template`` pages register without ``demo/demo.py``.
    """
    from reflex_django.routing import UrlRoutingMode, resolve_url_routing

    if resolve_url_routing() != UrlRoutingMode.DJANGO_LED:
        return

    from reflex_django.app_factory import ensure_django_led_app_ready
    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_rxconfig_from_django()
    ensure_django_led_app_ready()


def build_django_asgi() -> ASGIApp:
    """Return the Django ASGI application with staticfiles wrapping.

    Calls :func:`configure_django` and :func:`bootstrap_django_led_runtime` first so
    the caller does not need to manage Django bootstrapping. When
    ``django.contrib.staticfiles`` is in
    ``INSTALLED_APPS``, wraps the app with
    :class:`django.contrib.staticfiles.handlers.ASGIStaticFilesHandler`, which
    serves files under ``STATIC_URL`` while ``DEBUG=True`` (admin CSS/JS,
    user-provided static assets) and passes through to the inner app
    otherwise. With ``DEBUG=False`` it still routes ``STATIC_URL`` to a static
    file response from ``STATIC_ROOT`` (i.e. files collected by
    ``reflex django collectstatic``), so the same handler works in both modes.

    If staticfiles is not installed, the bare ASGI app is returned so users
    who deliberately skip staticfiles (e.g., admin disabled, no static
    assets) don't pay any overhead.

    Returns:
        The Django ASGI callable, optionally wrapped to serve static files.
    """
    configure_django()
    bootstrap_django_led_runtime()

    from django.conf import settings
    from django.core.asgi import get_asgi_application

    app = get_asgi_application()

    if "django.contrib.staticfiles" in getattr(settings, "INSTALLED_APPS", ()):
        from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

        return ASGIStaticFilesHandler(app)

    return app


def _normalize_prefix(prefix: str) -> str:
    """Normalize a path prefix to ``"/segment"`` (no trailing slash).

    Args:
        prefix: The raw prefix string from plugin configuration.

    Returns:
        The normalized prefix.

    Raises:
        ValueError: If ``prefix`` is empty.
    """
    if not prefix:
        msg = "Backend prefix must be a non-empty path like '/api'."
        raise ValueError(msg)
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if len(prefix) > 1 and prefix.endswith("/"):
        prefix = prefix.rstrip("/")
    return prefix


def _check_reserved(prefixes: tuple[str, ...]) -> None:
    """Reject prefixes that collide with Reflex's own endpoints."""
    for prefix in prefixes:
        if prefix == "/":
            msg = (
                "Backend prefix cannot be '/' — that would shadow the entire "
                "Reflex app. Use a sub-path like '/api' or '/admin'."
            )
            raise ValueError(msg)
        for reserved in RESERVED_REFLEX_PREFIXES:
            if prefix == reserved or prefix.startswith(reserved + "/"):
                msg = (
                    f"Backend prefix {prefix!r} collides with Reflex's "
                    f"reserved endpoint {reserved!r}. Pick a different prefix."
                )
                raise ValueError(msg)


def _path_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def _path_suffix_under_prefix(path: str, prefix: str) -> str:
    """Return the path remainder after ``prefix``, including a leading ``/``."""
    if path == prefix:
        return "/"
    return path[len(prefix) :]


def _is_reserved_reflex_subpath(path: str, prefix: str) -> bool:
    """True when ``path`` is under ``prefix`` but targets a Reflex-only endpoint."""
    suffix = _path_suffix_under_prefix(path, prefix)
    for reserved in RESERVED_REFLEX_PREFIXES:
        if suffix == reserved or suffix.startswith(reserved + "/"):
            return True
    return False


def _is_reserved_reflex_path(path: str) -> bool:
    """Return True when *path* targets a Reflex-internal endpoint."""
    for reserved in RESERVED_REFLEX_PREFIXES:
        if path == reserved or path.startswith(reserved + "/"):
            return True
    return False


def _should_route_to_django(scope: ASGIScope, path: str, prefixes: tuple[str, ...]) -> bool:
    """Decide whether an ASGI scope should be forwarded to Django."""
    scope_type = scope.get("type")
    if scope_type not in ("http", "websocket"):
        return False

    for prefix in prefixes:
        if not _path_matches(path, prefix):
            continue
        if scope_type == "http" and _is_reserved_reflex_subpath(path, prefix):
            return False
        return True
    return False


def _patch_http_only_static_mounts(app: ASGIApp) -> ASGIApp:
    """Replace frontend ``StaticFiles`` mounts so WebSockets do not match them.

    In production Reflex appends a catch-all ``Mount("/", StaticFiles(...))``.
    Starlette ``Mount.matches`` accepts WebSocket scopes, but ``StaticFiles``
    only handles HTTP and raises ``AssertionError`` otherwise. Patching those
    mounts to match HTTP only lets Socket.IO and other WebSocket routes work.
    """
    try:
        from starlette.applications import Starlette
        from starlette.routing import Match, Mount
        from starlette.staticfiles import StaticFiles
    except ImportError:
        return app

    if not isinstance(app, Starlette):
        return app

    class HttpOnlyMount(Mount):
        def matches(self, scope: ASGIScope) -> tuple[Any, ASGIScope]:
            if scope.get("type") != "http":
                return Match.NONE, {}
            return super().matches(scope)

    for index, route in enumerate(app.routes):
        if isinstance(route, Mount) and isinstance(route.app, StaticFiles):
            app.routes[index] = HttpOnlyMount(route.path, route.app, name=route.name)

    return app


def make_dispatcher(
    django_asgi: ASGIApp,
    *,
    backend_prefixes: tuple[str, ...],
    routing_mode: UrlRoutingMode = UrlRoutingMode.REFLEX_LED,
) -> Callable[[ASGIApp], ASGIApp]:
    """Build an ``api_transformer`` that routes by URL path prefix.

    Args:
        django_asgi: The Django ASGI callable to forward backend requests to.
        backend_prefixes: Path prefixes (e.g. ``("/api", "/admin")``) that
            should be served by Django. Prefixes that collide with Reflex's
            reserved endpoints raise :class:`ValueError`.
        routing_mode: :attr:`UrlRoutingMode.REFLEX_LED` (default) or
            :attr:`UrlRoutingMode.DJANGO_LED`. Both route ``backend_prefixes``
            to Django and other paths to Reflex; ``django_led`` additionally
            guarantees Reflex reserved paths never hit Django.

    Returns:
        A function ``transformer(reflex_asgi) -> ASGIApp`` that returns a
        dispatcher wrapping both apps.

    Raises:
        ValueError: If ``backend_prefixes`` is empty or any prefix collides
            with a reserved Reflex endpoint.
    """
    if not backend_prefixes:
        msg = "backend_prefixes must contain at least one prefix."
        raise ValueError(msg)

    normalized: tuple[str, ...] = tuple(
        _normalize_prefix(prefix) for prefix in backend_prefixes
    )
    _check_reserved(normalized)

    def transformer(reflex_asgi: ASGIApp) -> ASGIApp:
        reflex_asgi = _patch_http_only_static_mounts(reflex_asgi)

        async def dispatch(
            scope: ASGIScope, receive: ASGIReceive, send: ASGISend
        ) -> None:
            scope_type = scope.get("type")
            if scope_type == "lifespan":
                await reflex_asgi(scope, receive, send)
                return

            path = scope.get("path", "")

            if routing_mode == UrlRoutingMode.DJANGO_LED:
                if _is_reserved_reflex_path(path):
                    await reflex_asgi(scope, receive, send)
                    return
                if _should_route_to_django(scope, path, normalized):
                    await django_asgi(scope, receive, send)
                    return
                await reflex_asgi(scope, receive, send)
                return

            if _should_route_to_django(scope, path, normalized):
                await django_asgi(scope, receive, send)
                return

            await reflex_asgi(scope, receive, send)

        dispatch.backend_prefixes = normalized  # pyright: ignore[reportFunctionMemberAccess]
        dispatch.routing_mode = routing_mode  # pyright: ignore[reportFunctionMemberAccess]
        return dispatch

    transformer.backend_prefixes = normalized  # pyright: ignore[reportFunctionMemberAccess]
    transformer.routing_mode = routing_mode  # pyright: ignore[reportFunctionMemberAccess]
    return transformer
