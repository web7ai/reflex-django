"""Render the Reflex SPA shell through Django's template engine.

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER` (the default
single-port architecture), Django serves the SPA's ``index.html`` either
directly from ``STATIC_ROOT`` (production) or via the Vite reverse-proxy
(development). By default :mod:`reflex_django.views.mount` returns those
bytes verbatim, which means Django template tags like ``{{ request.user }}``,
``{{ csrf_token }}``, ``{{ messages }}``, ``{{ LANGUAGE_CODE }}``, and any
custom context-processor outputs do **not** render inside ``index.html``.

This module pipes the SPA HTML through Django's default
:class:`~django.template.engine.Engine` with
:class:`~django.template.context.RequestContext` so that:

- All ``settings.TEMPLATES[0]["OPTIONS"]["context_processors"]`` fire — for
  example ``django.contrib.auth.context_processors.auth`` makes ``user``
  available; ``django.template.context_processors.request`` makes
  ``request`` available; ``django.contrib.messages.context_processors.messages``
  makes ``messages`` available.
- ``{% csrf_token %}`` works, so SPA-side fetches to ``/admin/`` or custom
  Django form views can include a real CSRF cookie/token.
- ``{% load i18n %}`` / ``{% trans "..." %}`` and ``{% load static %}`` /
  ``{% static "..." %}`` work for the SPA shell itself.

Safety:

- Only HTML responses (``Content-Type`` starts with ``text/html``) are
  processed. JS bundles, CSS, source maps, and images are returned as-is.
- Template syntax errors fall back to the original HTML and emit a log
  warning — the page still loads even if the upstream output happens to
  contain raw ``{{`` / ``{%`` sequences that confuse Django's parser.
- The behaviour is gated by ``settings.REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE``
  (default ``True``).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("reflex_django.spa_template")

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


def _render_via_template_engine_enabled() -> bool:
    """Return ``True`` when the SPA shell should be templated.

    The env var ``REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE`` (``0`` / ``1``)
    takes precedence over the Django setting so that operators can flip the
    behaviour without editing ``settings.py``.
    """
    env = os.environ.get("REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    try:
        from django.conf import settings

        return bool(
            getattr(settings, "REFLEX_DJANGO_RENDER_SPA_VIA_TEMPLATE_ENGINE", True),
        )
    except Exception:
        return True


def _response_is_html(response: Any) -> bool:
    """Decide whether *response*'s body looks like HTML worth templating."""
    content_type = ""
    try:
        content_type = response.get("Content-Type", "")
    except Exception:
        return False
    return content_type.lower().split(";", 1)[0].strip() == "text/html"


def _extract_body(response: Any) -> bytes | None:
    """Return the response body as bytes, or ``None`` for streaming bodies."""
    if getattr(response, "streaming", False):
        return None
    body = getattr(response, "content", None)
    if isinstance(body, str):
        return body.encode("utf-8", errors="replace")
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    return None


def _decode_html(body: bytes) -> str:
    """Decode the upstream HTML body, preferring UTF-8 with replacement."""
    return body.decode("utf-8", errors="replace")


def _build_request_context(request: HttpRequest, html: str) -> Any:
    """Compile *html* with Django's default template engine and *request*'s context."""
    from django.template import engines

    engine = engines["django"]
    template = engine.from_string(html)
    return template.render(context=None, request=request)


def _compile_dev_live_reload_enabled() -> bool:
    return str(os.environ.get("REFLEX_DJANGO_COMPILE_DEV", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def compile_dev_reload_script(*, wait_for_ready: bool = False) -> str:
    """Return JS that polls the compile-dev build id and reloads when it changes."""
    from reflex_django._frontend_runner import BUILD_ID_PATH

    wait_init = "let last='missing';" if wait_for_ready else "let last=null;"
    reload_logic = (
        "if(wait){if(id!=='missing'&&id!==last)location.reload();"
        "if(id!=='missing')last=id;}"
        "else{if(id!=='missing'){if(last!==null&&id!==last)location.reload();last=id;}}"
    )
    return (
        "<script id=\"reflex-django-compile-dev-reload\">"
        "(function(){"
        f"{wait_init}const wait={str(wait_for_ready).lower()};const path={BUILD_ID_PATH!r};"
        "setInterval(async()=>{try{const r=await fetch(path,{cache:'no-store'});"
        f"const id=await r.text();{reload_logic}"
        "}catch(_){}},500);})();"
        "</script>"
    )


def compile_dev_waiting_html(backend_port: int) -> str:
    """HTML shown when compile-dev mode has no bundle on disk yet."""
    script = compile_dev_reload_script(wait_for_ready=True)
    return (
        "<!doctype html><html><head>"
        "<title>Reflex SPA building</title></head><body>"
        "<p>Reflex SPA bundle is not ready yet. "
        "<code>python manage.py run_reflex --env dev</code> compiles to "
        "<code>.web/</code> and runs Reflex's frontend build.</p>"
        f"<p>Waiting for the build to finish on "
        f"<a href=\"http://localhost:{backend_port}/\">"
        f"http://localhost:{backend_port}/</a>…</p>"
        f"{script}"
        "</body></html>"
    )


def _maybe_inject_compile_dev_live_reload(html: str) -> str:
    """Inject a lightweight full-page reload loop for compile-dev mode."""
    if not _compile_dev_live_reload_enabled():
        return html
    if "reflex-django-compile-dev-reload" in html:
        return html
    script = compile_dev_reload_script(wait_for_ready=False)
    lowered = html.lower()
    if "</body>" in lowered:
        idx = lowered.rfind("</body>")
        return html[:idx] + script + html[idx:]
    return html + script


def maybe_render_spa_html(
    request: HttpRequest,
    response: HttpResponse,
) -> HttpResponse:
    """Return *response* with its body re-rendered as a Django template.

    Args:
        request: The active :class:`~django.http.HttpRequest` (used to build
            the :class:`~django.template.RequestContext` so context processors
            fire).
        response: The upstream :class:`~django.http.HttpResponse` (either a
            file response from ``STATIC_ROOT`` or a proxied response from
            Vite).

    Returns:
        Either *response* unchanged (non-HTML, opted out, streaming body, or
        template error) or a fresh :class:`~django.http.HttpResponse` whose
        content has been processed by Django's template engine.
    """
    if not _render_via_template_engine_enabled():
        if _response_is_html(response):
            body = _extract_body(response)
            if body is not None:
                html = _decode_html(body)
                injected = _maybe_inject_compile_dev_live_reload(html)
                if injected != html:
                    from django.http import HttpResponse

                    return HttpResponse(
                        injected,
                        status=response.status_code,
                        content_type=response.get("Content-Type")
                        or "text/html; charset=utf-8",
                    )
        return response
    if not _response_is_html(response):
        return response
    body = _extract_body(response)
    if body is None:
        return response

    html = _decode_html(body)
    try:
        rendered = _build_request_context(request, html)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Reflex SPA template render failed for %s (%s); serving original HTML.",
            getattr(request, "path", "<unknown>"),
            exc.__class__.__name__,
        )
        return response

    rendered = _maybe_inject_compile_dev_live_reload(rendered)

    from django.http import HttpResponse

    new_response = HttpResponse(
        rendered,
        status=response.status_code,
        content_type=response.get("Content-Type") or "text/html; charset=utf-8",
    )
    # Preserve upstream headers that aren't body-size-dependent so the SPA
    # shell still sees things like Vite's HMR notice cookies, Set-Cookie
    # CSRF tokens, etc.
    for key, value in response.items():
        lk = key.lower()
        if lk in {"content-length", "content-encoding", "transfer-encoding"}:
            continue
        if lk == "content-type":
            continue
        new_response[key] = value
    return new_response


__all__ = [
    "_render_via_template_engine_enabled",
    "_response_is_html",
    "maybe_render_spa_html",
]
