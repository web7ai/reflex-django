"""Catch-all Django view that serves the Reflex SPA shell.



When ``DEBUG=True``, optionally reverse-proxies to the Vite dev server when

``RX_DEV_PROXY=1``. Otherwise serves the compiled SPA from disk.

"""

from __future__ import annotations
import logging
import mimetypes
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseNotFound
from django.views import View
from reflex_django.dev.proxy import (
    _dev_vite_target_or_none,
    _resolve_backend_port_from_config,
    _resolve_frontend_port_from_config,
    dev_proxy_explicitly_enabled,
    dev_uses_separate_ports,
    reverse_proxy_to_vite,
)
from reflex_django.mount.spa_paths import resolve_spa_index, spa_root_candidates
from reflex_django.mount.spa_template import maybe_render_spa_html

if TYPE_CHECKING:

    from collections.abc import Iterable


logger = logging.getLogger("reflex_django.views.mount")


def _resolve_spa_asset(request_path: str) -> Path | None:
    """Return a real file path for ``request_path`` under one of the SPA roots.



    Tries each SPA root in order; for every root, probes (in order) the

    request path itself, then the pre-rendered route variants emitted by

    Reflex SSR builds (``<path>.html`` and ``<path>/index.html``). The

    ``.html``/``index.html`` fallbacks let SSR-built sites serve their

    pre-rendered per-route HTML (for example ``profile.html`` for

    ``/profile``) instead of unconditionally falling back to the root

    ``index.html`` shell — which would show the wrong page on every

    deep-link.



    Args:

        request_path: URL path including a leading slash (``/index.html``,

            ``/static/main.js``).



    Returns:

        The resolved file path if it exists and is inside the SPA root, else

        ``None`` (falls back to ``index.html`` for SPA history routing).

    """

    rel = request_path.lstrip("/")

    if not rel or rel.endswith("/"):

        rel = (rel + "index.html").lstrip("/")

    candidates_rel: list[str] = [rel]

    if not rel.endswith(".html") and not rel.endswith("/index.html"):

        candidates_rel.append(f"{rel}.html")

        candidates_rel.append(f"{rel}/index.html")

    for root in spa_root_candidates():

        try:

            root_resolved = root.resolve()

        except OSError:

            continue

        for candidate_rel in candidates_rel:

            try:

                candidate = (root / candidate_rel).resolve()

            except OSError:

                continue

            if root_resolved not in candidate.parents and candidate != root_resolved:

                continue

            if candidate.is_file():

                return candidate

    return None


def _serve_spa_response(request_path: str) -> HttpResponse:
    """Serve an asset from the SPA bundle or fall back to ``index.html``.



    Args:

        request_path: The request path including the leading slash.



    Returns:

        A :class:`~django.http.FileResponse` for binary/JS/CSS assets,

        a plain :class:`~django.http.HttpResponse` with the bytes of an

        HTML asset (so it can be templated by

        :mod:`reflex_django.mount.spa_template`), or a 404 if nothing is found.

    """

    asset = _resolve_spa_asset(request_path)

    if asset is None:

        index = resolve_spa_index()

        if index is None:

            try:

                from django.conf import settings as django_settings

                debug = getattr(django_settings, "DEBUG", False)

            except Exception:

                debug = False

            if debug:

                if dev_uses_separate_ports():

                    msg = (
                        "Reflex SPA is served on the Vite frontend port in "
                        "two-port dev mode. Open "
                        f"http://localhost:{_resolve_frontend_port_from_config() or 3000}/ "
                        "for the UI, or use "
                        "`reflex run` to browse "
                        "the backend port with Vite reverse-proxied through Django."
                    )

                elif _compile_dev_mode_enabled():

                    backend_port = _resolve_backend_port_from_config() or 8000

                    from reflex_django.mount.spa_template import (
                        compile_dev_waiting_html,
                    )

                    return HttpResponse(
                        compile_dev_waiting_html(backend_port),
                        content_type="text/html; charset=utf-8",
                        status=503,
                    )

                elif dev_proxy_explicitly_enabled():

                    msg = (
                        "Reflex SPA frontend bundle not found and the Vite dev "
                        "server is not reachable. Run "
                        "`reflex run` (not bare "
                        "`runserver`/`uvicorn`) and wait for Vite to start, "
                        f"then open http://localhost:{_resolve_frontend_port_from_config() or 8000}/."
                    )

                else:

                    msg = (
                        "Reflex SPA frontend bundle not found on disk "
                        "(expected `index.html` under `.web/build/client`, "
                        "`.web/_static`, or `STATIC_ROOT/_reflex`). Run "
                        "`reflex run` and wait for "
                        "the export to finish, or build manually with "
                        "`reflex export`. For Vite hot reload, "
                        "use `reflex run` and "
                        f"open http://localhost:{_resolve_frontend_port_from_config() or 3000}/."
                    )

            else:

                msg = (
                    "Reflex SPA bundle not found. Run `reflex export` and "
                    "`manage.py collectstatic` for production, or run "
                    "`reflex run` for development."
                )

            return HttpResponseNotFound(msg, content_type="text/plain")

        asset = index

    mime, _ = mimetypes.guess_type(str(asset))

    if asset.suffix == ".mjs":

        content_type = "text/javascript"

    else:

        content_type = mime or "application/octet-stream"

    # Materialize HTML responses so :func:`maybe_render_spa_html` can run

    # them through Django's template engine. Streaming the file would skip

    # templating entirely (see ``response.streaming`` in spa_template).

    if content_type.startswith("text/html"):

        return HttpResponse(
            asset.read_bytes(),
            content_type="text/html; charset=utf-8",
        )

    return FileResponse(asset.open("rb"), content_type=content_type)


_LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "::1"})


# Latch so the self-loop warning is emitted at most once per process instead

# of on every request (favicon, assets, page loads …).

_dev_proxy_self_loop_handled = False


def _disable_dev_proxy_after_self_loop(target: str) -> None:
    """Turn the dev proxy off process-wide after detecting a self-loop.



    Running the ASGI app standalone (no separate Vite) with ``DEBUG=True``

    makes the dev proxy point back at this server. Rather than re-checking and

    re-warning on every request, we set ``RX_DEV_PROXY=0`` so

    :func:`reflex_django.dev.proxy._dev_vite_target_or_none` returns ``None``

    from here on, and the app serves the compiled SPA from disk like prod.

    The warning is logged only once.

    """

    global _dev_proxy_self_loop_handled

    os.environ["RX_DEV_PROXY"] = "0"

    if _dev_proxy_self_loop_handled:

        return

    _dev_proxy_self_loop_handled = True

    logger.warning(
        "Vite dev-proxy target %s points back at this server (no separate "
        "Vite running). Disabling the dev proxy and serving the compiled SPA "
        "from disk for the rest of this process. To avoid this entirely, run "
        "with DEBUG=False or set RX_DEV_PROXY=0 for standalone/prod "
        "serving, or use `reflex run` for the dev loop.",
        target,
    )


# When Vite is reachable-in-principle (dev proxy on) but not actually running,

# every proxied request pays a full TCP connect + failure before we fall back

# to disk — and logs a warning. To keep the disk fallback fast and quiet, we

# back off: after one failed connect we serve from disk directly for a short

# cooldown, retry once the window elapses, and auto-recover when Vite returns.

_VITE_UNREACHABLE_COOLDOWN_S = 5.0

_vite_unreachable_until: float = 0.0

_vite_unreachable_logged: bool = False


def _vite_in_cooldown() -> bool:
    """Return True while we're skipping proxy attempts after a failed connect."""

    return time.monotonic() < _vite_unreachable_until


def _mark_vite_unreachable(target: str) -> None:
    """Start/extend the disk-fallback cooldown and log once per outage."""

    global _vite_unreachable_until, _vite_unreachable_logged

    _vite_unreachable_until = time.monotonic() + _VITE_UNREACHABLE_COOLDOWN_S

    if _vite_unreachable_logged:

        return

    _vite_unreachable_logged = True

    logger.warning(
        "Vite unreachable at %s; serving the compiled SPA from disk and "
        "pausing proxy attempts for ~%.0fs (will retry automatically). This "
        "is expected when the ASGI server runs without a separate Vite dev "
        "server — use `reflex run` for HMR, or set "
        "DEBUG=False / RX_DEV_PROXY=0 to serve from disk silently.",
        target,
        _VITE_UNREACHABLE_COOLDOWN_S,
    )


def _mark_vite_reachable() -> None:
    """Clear the cooldown once a proxy attempt succeeds again."""

    global _vite_unreachable_until, _vite_unreachable_logged

    if _vite_unreachable_logged:

        logger.info("Vite reachable again; resuming the HMR dev proxy.")

    _vite_unreachable_until = 0.0

    _vite_unreachable_logged = False


def _vite_starting_response(target: str) -> HttpResponse:
    """Return 503 while the Vite dev server is still booting or unreachable."""

    return HttpResponse(
        "reflex-django: Vite dev server is starting or unreachable at "
        f"{target}. Retry in a moment, or run `reflex run` "
        "to start the dev loop.",
        status=503,
        content_type="text/plain",
    )


def _dev_proxy_target_is_self(request: HttpRequest, target: str) -> bool:
    """Return True when the dev-proxy target points back at this same server.



    Running the ASGI app directly (e.g. ``uvicorn backend.asgi:application

    --port 3000``) without a separate Vite server is a common production-style

    invocation. If the resolved Vite target happens to be the same

    host:port the request arrived on (classically because the backend was

    started on the default Vite port ``3000``), reverse-proxying would loop

    the server back into itself, spinning until it 502s. Detecting that lets

    us fall back to serving the compiled SPA from disk instead.

    """

    try:

        parts = urlsplit(target)

        target_port = parts.port

        if target_port is None:

            return False

        if str(target_port) != str(request.get_port()):

            return False

        return (parts.hostname or "").lower() in _LOCAL_HOSTNAMES

    except Exception:  # noqa: BLE001

        return False


class ReflexMountView(View):
    """Catch-all view for Reflex-owned URL space served by Django.



    Dev mode may reverse-proxy to Vite; prod mode serves the compiled SPA

    from staticfiles.

    """

    http_method_names = ["get", "head", "options"]

    async def _handle(
        self,
        request: HttpRequest,
    ) -> HttpResponse:

        target = _dev_vite_target_or_none()

        if target is not None and _dev_proxy_target_is_self(request, target):

            _disable_dev_proxy_after_self_loop(target)

            target = None

        force_vite_proxy = dev_proxy_explicitly_enabled()

        if target is not None and _vite_in_cooldown():

            # We recently saw Vite down; skip the (slow) connect attempt.

            if force_vite_proxy:

                response = _vite_starting_response(target)

            else:

                # Serve the compiled bundle from disk when dev proxy is off.

                response = _serve_spa_response(request.path)

        elif target is not None:

            response = await reverse_proxy_to_vite(request, target)

            # ``reverse_proxy_to_vite`` returns 502 when Vite is unreachable

            # (e.g. the ASGI app is run standalone, prod-style, with no Vite).

            if getattr(response, "status_code", None) == 502:

                _mark_vite_unreachable(target)

                if force_vite_proxy:

                    response = _vite_starting_response(target)

                else:

                    response = _serve_spa_response(request.path)

            else:

                _mark_vite_reachable()

        elif dev_uses_separate_ports():

            response = HttpResponseNotFound()

        else:

            response = _serve_spa_response(request.path)

        # Pipe HTML responses through Django's template engine so

        # ``{{ request.user }}``, ``{% csrf_token %}``, ``{{ messages }}``,

        # ``{% load i18n %}``, and any custom context-processor keys render

        # inside the SPA shell. Non-HTML assets pass through untouched.

        return maybe_render_spa_html(request, response)

    async def get(  # type: ignore[override]
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:

        del args, kwargs

        return await self._handle(request)

    async def head(  # type: ignore[override]
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:

        response = await self.get(request, *args, **kwargs)

        response.content = b""

        return response


__all__ = ["ReflexMountView"]
