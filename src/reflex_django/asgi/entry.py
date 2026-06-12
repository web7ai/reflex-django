"""ASGI entry point for the Django-outer, single-port architecture.

Use this as the WSGI/ASGI ``application`` in production:

.. code-block:: python

    # config/asgi.py
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    from reflex_django.asgi.entry import application  # noqa: F401

then run with any ASGI server:

.. code-block:: bash

    uvicorn config.asgi:application --host 0.0.0.0 --port 8000

In :class:`~reflex_django.setup.routing.UrlRoutingMode.DJANGO_OUTER` (the new
default), Django owns the outer ASGI app, lifespan is forwarded to Reflex,
and the Socket.IO/upload/health endpoints are mounted as ASGI sub-apps
under Django via :class:`~reflex_django.asgi.django_outer.DjangoOuterDispatcher`.
In legacy ``reflex_led`` or ``django_led`` modes, this entry point falls
back to building the Reflex-outer stack with the same Django dispatcher
that :mod:`reflex_django.asgi.app` provided before.
"""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from reflex_django.asgi.app import ASGIApp, django_asgi_application
from reflex_django.asgi.django_outer import (
    DEFAULT_RESERVED_REFLEX_PREFIXES,
    DjangoOuterDispatcher,
)
from reflex_django.setup.routing import UrlRoutingMode, resolve_url_routing

if TYPE_CHECKING:
    from reflex.app import App

logger = logging.getLogger("reflex_django.asgi.entry")


_REFLEX_FRONTEND_MOUNT_ENV = "REFLEX_MOUNT_FRONTEND_COMPILED_APP"

_AUTO_EXPORT_ON_START_ENV = "REFLEX_DJANGO_AUTO_EXPORT_ON_START"


def _auto_export_on_start_enabled() -> bool:
    """Return whether the startup "build SPA if missing" hook is enabled.

    Honours the env var ``REFLEX_DJANGO_AUTO_EXPORT_ON_START`` first (so
    operators and ``manage.py run_reflex`` can toggle it without editing
    settings), then ``settings.REFLEX_DJANGO_AUTO_EXPORT_ON_START``. Defaults
    to True so a raw ``uvicorn ...:application`` boot serves a real SPA out of
    the box.
    """
    env = os.environ.get(_AUTO_EXPORT_ON_START_ENV)
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    try:
        from django.conf import settings

        return bool(getattr(settings, _AUTO_EXPORT_ON_START_ENV, True))
    except Exception:  # noqa: BLE001
        return True


def _spa_bundle_missing() -> bool:
    """Return True when no compiled SPA ``index.html`` is discoverable on disk.

    Uses the same discovery paths as
    :class:`reflex_django.views.mount.ReflexMountView` so the pre-flight check
    matches what the runtime view will actually serve. Errors are treated as
    "missing" so we err on the side of (re)building.
    """
    try:
        from reflex_django.mount.spa_paths import resolve_spa_index

        return resolve_spa_index() is None
    except Exception:  # noqa: BLE001
        return True


def _maybe_auto_export_spa() -> None:
    """Build the SPA bundle once at startup when it is missing from disk.

    The canonical production entry point is a raw ASGI server
    (``uvicorn backend.asgi:application``). When the operator hasn't run
    ``reflex export`` + ``manage.py collectstatic`` yet,
    :class:`~reflex_django.views.mount.ReflexMountView` 404s every request with
    "Reflex SPA bundle not found", which makes a deploy fail confusingly.
    Rather than make that a hard blocker, build the bundle once here so the
    app boots serving a real SPA.

    This is best-effort: build failures are logged but never raised, so the
    server still starts (and falls back to any existing bundle, or the helpful
    404 if there genuinely is nothing). ``manage.py run_reflex`` disables this
    via ``REFLEX_DJANGO_AUTO_EXPORT_ON_START=0`` because it owns builds itself.
    """
    if not _auto_export_on_start_enabled():
        return
    if not _spa_bundle_missing():
        return
    try:
        from django.core.management import call_command
    except Exception as exc:  # noqa: BLE001
        logger.warning("reflex-django: cannot auto-export SPA at startup (%r).", exc)
        return

    logger.warning(
        "reflex-django: no compiled SPA bundle found on disk; building it once "
        "now so the ASGI server can serve it. To pre-build in CI (faster, "
        "deterministic boot), run `python manage.py export_reflex "
        "--frontend-only --no-zip --stage-to-static-root` (and "
        "`collectstatic`) before starting the server, or set "
        "REFLEX_DJANGO_AUTO_EXPORT_ON_START=0 to disable this."
    )
    try:
        call_command(
            "export_reflex",
            frontend_only=True,
            no_zip=True,
            stage_to_static_root=True,
            env="prod",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "reflex-django: startup SPA auto-export failed (%r). The server "
            "will fall back to any existing bundle on disk; otherwise requests "
            "will 404 with a hint. Build manually with `manage.py "
            "export_reflex` or set REFLEX_DJANGO_AUTO_EXPORT_ON_START=0.",
            exc,
        )


from reflex_django.dev.proxy import dev_proxy_explicitly_enabled as _dev_proxy_explicitly_enabled


def _vite_target_reachable(target: str, timeout: float = 0.5) -> bool:
    """Return True when a TCP connection to the Vite target succeeds quickly."""
    parts = urlsplit(target)
    host = parts.hostname or "127.0.0.1"
    port = parts.port
    if port is None:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _maybe_disable_dev_proxy_without_vite() -> None:
    """Disable the dev proxy at startup when no Vite dev server is running.

    A raw ``uvicorn ...:application`` boot with ``DEBUG=True`` leaves the dev
    proxy enabled, so every request tries (and fails) to reach Vite before
    falling back to disk — producing noisy per-request ``ConnectError`` logs.
    When the proxy is on only by the ``DEBUG`` default (not explicitly forced
    via ``REFLEX_DJANGO_DEV_PROXY=1``) and nothing is listening at the target,
    switch the whole process to serve the compiled SPA from disk so it behaves
    like prod — quietly and without the per-request connect overhead.

    Skipped entirely when the proxy is already off (returns ``None`` target)
    or when explicitly forced on (``manage.py run_reflex`` does this; Vite may
    still be coming up, so we must not pre-emptively disable it there).
    """
    try:
        from reflex_django.dev.proxy import _dev_vite_target_or_none

        target = _dev_vite_target_or_none()
    except Exception:  # noqa: BLE001
        return
    if target is None or _dev_proxy_explicitly_enabled():
        return
    if _vite_target_reachable(target):
        return

    os.environ["REFLEX_DJANGO_DEV_PROXY"] = "0"
    logger.warning(
        "reflex-django: dev proxy is on (DEBUG=True) but no Vite dev server is "
        "reachable at %s; serving the compiled SPA from disk for this process "
        "(prod-style). Run `python manage.py run_reflex` for HMR, or set "
        "DEBUG=False / REFLEX_DJANGO_DEV_PROXY=0 to silence this explicitly.",
        target,
    )


def _unwrap_reflex_inner_asgi(rx_app: App) -> ASGIApp:
    """Return Reflex's inner ASGI app (Starlette with Socket.IO etc.) for mounting.

    Reflex normally wraps ``app._api`` in :meth:`reflex.app.App._context_middleware`
    and a top-level Starlette that owns lifespan. In ``DJANGO_OUTER`` mode we
    own lifespan ourselves (see
    :class:`~reflex_django.asgi.django_outer.DjangoOuterDispatcher`), so
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
    if _REFLEX_FRONTEND_MOUNT_ENV not in os.environ:
        os.environ[_REFLEX_FRONTEND_MOUNT_ENV] = "0"


def _build_reflex_outer_application() -> ASGIApp:
    """Build the Reflex-outer ASGI app (``reflex_led`` / ``reflex_outer``)."""
    from reflex_django.runtime.app_factory import ensure_django_led_app_ready
    from reflex_django.asgi.http_proxy import make_django_http_proxy
    from reflex_django.asgi.http_subprocess import (
        resolve_django_http_upstream,
        wrap_reflex_asgi_with_django_http_lifecycle,
    )
    from reflex_django.runtime.integration import install_reflex_django_integration
    from reflex_django.mount.prefixes import resolve_prefixes
    from reflex_django.asgi.reflex_outer import ReflexOuterDispatcher

    install_reflex_django_integration()
    rx_app = ensure_django_led_app_ready()
    reflex_inner = rx_app()
    prefix_config = resolve_prefixes()
    dispatcher = ReflexOuterDispatcher(
        reflex=reflex_inner,
        django=make_django_http_proxy(resolve_django_http_upstream()),
        django_prefixes=prefix_config.backend_prefixes_for_asgi(),
    )
    return wrap_reflex_asgi_with_django_http_lifecycle(dispatcher)


def build_django_outer_application() -> ASGIApp:
    """Compose Django-outer ASGI app for single-port deployment.

    Steps:

    1. Run the standard integration bootstrap (Django settings, get_config
       patch, Reflex CLI layout, page imports).
    2. Build the Reflex app via the existing factory; the plugin's
       ``post_compile`` runs but skips :attr:`reflex.app.App.api_transformer`
       wiring in ``DJANGO_OUTER`` mode (see
       :meth:`reflex_django.setup.plugin.ReflexDjangoPlugin._configure`).
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

    from reflex_django.runtime.app_factory import ensure_django_led_app_ready
    from reflex_django.runtime.integration import install_reflex_django_integration

    install_reflex_django_integration()
    rx_app = ensure_django_led_app_ready()

    # When the app is run standalone (raw ASGI server) with DEBUG=True but no
    # Vite dev server, turn the dev proxy off up front so we serve from disk
    # silently instead of failing a proxy connect on every request.
    _maybe_disable_dev_proxy_without_vite()

    # With the integration installed and the app compiled, build the SPA
    # bundle once if it's missing so a raw ``uvicorn ...:application`` prod
    # boot serves a real SPA instead of 404ing. No-op when a bundle already
    # exists or when disabled (e.g. by ``manage.py run_reflex``).
    _maybe_auto_export_spa()

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
# bare ``import reflex_django.asgi.entry`` does not import Django/Reflex
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
