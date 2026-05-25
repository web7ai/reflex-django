"""Catch-all Django view that serves the Reflex SPA shell.

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER` (the default),
this view is the entry point Django uses for every non-Reflex, non-Django
request:

- ``DEBUG=True``: reverse-proxy to the Vite dev server so users only see one
  port even though Vite still runs on its own for hot-module reload.
- ``DEBUG=False``: serve the SPA bundle compiled by ``reflex export`` and
  collected into ``STATIC_ROOT`` by ``manage.py collectstatic``.

In the legacy Reflex-led modes, the ASGI dispatcher forwards SPA requests
to Reflex directly; this view should not normally be hit. It returns a
helpful 501 in that case for visibility.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseNotFound,
)
from django.views import View

from reflex_django.dev_proxy import (
    _dev_vite_target_or_none,
    reverse_proxy_to_vite,
)
from reflex_django.routing import UrlRoutingMode, resolve_url_routing
from reflex_django.spa_template import maybe_render_spa_html

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger("reflex_django.views.mount")


_SPA_DIR_CANDIDATES: tuple[str, ...] = ("_reflex", "_static", "reflex")


def _spa_root_candidates() -> Iterable[Path]:
    """Yield directories on disk that may hold the compiled Reflex SPA.

    The discovery order matters — the first match wins. We try staging
    directories first (``STATIC_ROOT/_reflex`` etc., populated by
    ``manage.py export_reflex --stage-to-static-root`` or ``collectstatic``),
    then fall back to the in-place Reflex build outputs:

    - ``.web/build/client/`` — SSR-enabled builds (current Reflex default;
      Vite SSR puts the client bundle here and pre-renders pages
      alongside).
    - ``.web/_static/`` — ``--no-ssr`` builds and pre-SSR Reflex versions.
    - ``.web/build/`` — some intermediate Reflex versions.
    """
    try:
        from django.conf import settings
    except Exception:
        return ()

    roots: list[Path] = []
    static_root = getattr(settings, "STATIC_ROOT", None)
    if static_root:
        base = Path(static_root)
        for sub in _SPA_DIR_CANDIDATES:
            roots.append(base / sub)
        roots.append(base)

    project = getattr(settings, "BASE_DIR", None)
    if project:
        base = Path(project)
        # SSR-enabled builds (Vite SSR layout: client bundle + pre-rendered HTML).
        roots.append(base / ".web" / "build" / "client")
        # Legacy/no-SSR builds.
        roots.append(base / ".web" / "_static")
        roots.append(base / ".web" / "build")

    seen: set[Path] = set()
    out: list[Path] = []
    for r in roots:
        try:
            resolved = r.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(r)
    return out


def _resolve_spa_asset(request_path: str) -> Path | None:
    """Return a real file path for ``request_path`` under one of the SPA roots.

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

    for root in _spa_root_candidates():
        try:
            candidate = (root / rel).resolve()
            root_resolved = root.resolve()
        except OSError:
            continue
        if root_resolved not in candidate.parents and candidate != root_resolved:
            continue
        if candidate.is_file():
            return candidate
    return None


def _resolve_spa_index() -> Path | None:
    """Return the compiled SPA's ``index.html`` path, or ``None`` if missing."""
    for root in _spa_root_candidates():
        candidate = root / "index.html"
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
        :mod:`reflex_django.spa_template`), or a 404 if nothing is found.
    """
    asset = _resolve_spa_asset(request_path)
    if asset is None:
        index = _resolve_spa_index()
        if index is None:
            return HttpResponseNotFound(
                "Reflex SPA bundle not found. Run `reflex export` and "
                "`manage.py collectstatic` for production, or run "
                "`manage.py run_reflex` for development.",
                content_type="text/plain",
            )
        asset = index

    mime, _ = mimetypes.guess_type(str(asset))
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


class ReflexMountView(View):
    """Catch-all view for Reflex-owned URL space served by Django.

    Behavior depends on the active :class:`UrlRoutingMode`:

    - :attr:`UrlRoutingMode.DJANGO_OUTER` (default): dev mode reverse-proxies
      to Vite; prod mode serves the compiled SPA from staticfiles.
    - Other modes (Reflex-led): Django should not be handling this path; we
      return 501 to make misconfiguration obvious.
    """

    http_method_names = ["get", "head", "options"]

    async def _handle_django_outer(
        self,
        request: HttpRequest,
    ) -> HttpResponse:
        target = _dev_vite_target_or_none()
        if target is not None:
            response = await reverse_proxy_to_vite(request, target)
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
        if resolve_url_routing() == UrlRoutingMode.DJANGO_OUTER:
            return await self._handle_django_outer(request)
        return HttpResponse(
            "This URL is served by the Reflex application. "
            "Use `python manage.py run_reflex` for local development "
            "or switch to REFLEX_DJANGO_URL_ROUTING='django_outer' for "
            "the single-port architecture.",
            status=501,
            content_type="text/plain",
        )

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
