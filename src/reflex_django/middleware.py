"""Bridge Django auth/session middleware into Reflex's event flow.

Reflex events arrive over Socket.IO and never traverse Django's HTTP request
path, so Django middleware like
:class:`django.contrib.sessions.middleware.SessionMiddleware` and
:class:`django.contrib.auth.middleware.AuthenticationMiddleware` never run for
them. This module bridges that gap:

- :class:`DjangoEventBridge` is a :class:`reflex.middleware.Middleware`
  subclass whose ``preprocess`` runs before every Reflex event.
- It synthesizes a :class:`django.http.HttpRequest` from
  ``event.router_data`` (cookies, headers, client IP), loads the session from
  the configured cookie, populates ``request.user`` via
  :func:`django.contrib.auth.get_user`, and stashes the request on the
  :mod:`reflex_django.context` contextvar (see :func:`begin_event_request`).
- Handlers can then call :func:`reflex_django.current_user` etc. without
  needing direct access to the event payload.
- When ``USE_I18N`` and ``REFLEX_DJANGO_I18N_EVENT_BRIDGE`` are true, it also
  applies :class:`django.middleware.locale.LocaleMiddleware` logic so
  :func:`django.utils.translation.get_language` and ``request.LANGUAGE_CODE``
  match normal Django negotiation (session, cookie, ``Accept-Language``).

The bridge is intentionally narrow: it does not run arbitrary user-defined
Django middleware (which expects ``__call__(request)`` to return an
``HttpResponse``). Users who need behavior from a specific Django middleware
class should call into it directly from this module's hook points or write a
small adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex.middleware import Middleware
from reflex_django.conf import configure_django
from reflex_django.context import (
    begin_event_request,
    begin_event_response,
    end_event_request,
    end_event_response,
)

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from reflex_base.event import Event
    from starlette.requests import Request

    from reflex.app import App
    from reflex.state import BaseState, StateUpdate


def _router_data_from_starlette_request(request: Request) -> dict[str, Any]:
    """Build ``router_data`` from a Starlette upload HTTP request.

    Args:
        request: The incoming ``/_upload`` request (includes browser cookies).

    Returns:
        A dict compatible with :func:`_build_request_from_router_data`.
    """
    cookie_header = request.headers.get("cookie", "")
    if not cookie_header and request.cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in request.cookies.items())

    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        headers[key.lower()] = value
    if cookie_header:
        headers["cookie"] = cookie_header

    client_ip = ""
    if request.client is not None:
        client_ip = request.client.host or ""

    query: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        query[str(key)] = str(value)

    return {
        "headers": headers,
        "ip": client_ip,
        "pathname": request.url.path,
        "query": query,
    }


def _router_data_is_usable(router_data: dict[str, Any]) -> bool:
    """Return whether *router_data* has enough fields to synthesize a request."""
    if not router_data:
        return False
    headers = router_data.get("headers")
    if isinstance(headers, dict) and headers:
        return True
    return bool(
        router_data.get("pathname")
        or router_data.get("ip")
        or router_data.get("query")
    )


def _router_data_from_state_chain(state: Any) -> dict[str, Any]:
    """Return the nearest non-empty ``router_data`` on the state tree.

    Upload handlers often run on substates (e.g. ``ProfileState``); cookies live
    on the root state's ``router_data`` and are visible via inheritance in handlers
    but must be resolved explicitly for the event bridge.
    """
    if state is None:
        return {}

    from unittest.mock import Mock

    if isinstance(state, Mock):
        return {}

    try:
        root = state._get_root_state()  # noqa: SLF001
    except (AttributeError, TypeError):
        root = state

    if isinstance(root, Mock):
        return {}

    seen: set[int] = set()
    node: Any = root
    max_hops = 64
    while node is not None and id(node) not in seen and max_hops > 0:
        max_hops -= 1
        seen.add(id(node))
        if isinstance(node, Mock):
            break
        raw = getattr(node, "router_data", None)
        if isinstance(raw, dict) and _router_data_is_usable(raw):
            return raw
        parent = getattr(node, "parent_state", None)
        if parent is None or isinstance(parent, Mock):
            break
        node = parent
    return {}


def _merge_router_data_with_state_cookie(
    state_rd: dict[str, Any],
    event_rd: dict[str, Any],
) -> dict[str, Any]:
    """Shallow-merge router data but keep state ``Cookie`` when the event omits it."""
    merged = {**state_rd, **event_rd}
    state_headers = dict(state_rd.get("headers") or {})
    event_headers = dict(event_rd.get("headers") or {})
    if not event_headers.get("cookie") and state_headers.get("cookie"):
        event_headers["cookie"] = state_headers["cookie"]
    merged["headers"] = {**state_headers, **event_headers}
    return merged


def _resolve_router_data(event: Event, state: BaseState | None) -> dict[str, Any]:
    """Merge event and state ``router_data``, preferring event cookies when set.

    Upload events from Reflex often omit ``router_data``; persisted
    ``state.router_data`` from prior Socket.IO events may still carry the session
    cookie as a fallback.

    Args:
        event: The incoming Reflex event.
        state: Client state from the event processor (may hold prior ``router_data``).

    Returns:
        Effective router data for the Django event bridge.
    """
    raw_event_rd = getattr(event, "router_data", None)
    event_rd: dict[str, Any] = raw_event_rd if isinstance(raw_event_rd, dict) else {}
    if _router_data_is_usable(event_rd) and (event_rd.get("headers") or {}).get("cookie"):
        return event_rd

    state_rd = _router_data_from_state_chain(state)
    if _router_data_is_usable(state_rd):
        return _merge_router_data_with_state_cookie(state_rd, event_rd)

    if _router_data_is_usable(event_rd):
        return event_rd

    return state_rd


def _split_host_port(host_header: str) -> tuple[str, str]:
    """Return ``(server_name, server_port)`` parsed from a ``Host:`` header."""
    if not host_header:
        return ("localhost", "80")
    host = host_header.strip()
    if host.startswith("["):  # IPv6
        end = host.find("]")
        if end == -1:
            return (host, "80")
        name = host[: end + 1]
        port_part = host[end + 1 :].lstrip(":")
        return (name, port_part or "80")
    if ":" in host:
        name, _, port = host.partition(":")
        return (name or "localhost", port or "80")
    return (host, "80")


def _scheme_from_headers(headers: dict[str, str]) -> str:
    proto = (
        headers.get("x-forwarded-proto")
        or headers.get("X-Forwarded-Proto")
        or ""
    )
    if proto:
        return str(proto).strip().lower().split(",")[0]
    return "http"


def _resolve_url_match(path: str) -> Any | None:
    """Best-effort URL resolution for the synthetic event request.

    When ``ROOT_URLCONF`` is set we run :func:`django.urls.resolve` to
    populate ``request.resolver_match`` — handy for middleware that
    inspects view kwargs or namespaces (e.g. login-required gates).
    Failures are swallowed so anonymous-event paths or pages that no
    longer exist do not break event processing.
    """
    try:
        from django.urls import resolve
    except Exception:
        return None
    try:
        return resolve(path)
    except Exception:
        return None


def _populate_post_from_payload(
    request: HttpRequest,
    router_data: dict[str, Any],
) -> None:
    """Optionally feed event payload kwargs into ``request.POST``.

    Off by default. Opt in with
    ``REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD = True`` so middleware that
    treats POST like a form (rare for Reflex events) sees the same data
    the handler will.
    """
    try:
        from django.conf import settings
    except Exception:
        return
    if not getattr(settings, "REFLEX_DJANGO_EVENT_POST_FROM_PAYLOAD", False):
        return

    payload = router_data.get("payload")
    if not isinstance(payload, dict):
        return

    from django.http import QueryDict

    qd = QueryDict(mutable=True)
    for key, value in payload.items():
        if value is None:
            continue
        try:
            qd[str(key)] = str(value)
        except Exception:
            continue
    request.POST = qd  # pyright: ignore[reportAttributeAccessIssue]


def _build_request_from_router_data(router_data: dict[str, Any]) -> HttpRequest:
    """Build a fully-populated Django HttpRequest from Reflex ``router_data``.

    The request mirrors what an HTTP request to the same path would look
    like: ``method``, ``path``, ``GET``, ``COOKIES``, ``META`` (including
    ``HTTP_*`` headers, ``REMOTE_ADDR``, ``SERVER_NAME``, ``SERVER_PORT``,
    ``wsgi.url_scheme``), ``scheme`` (and the matching ``is_secure()``
    semantics via ``META[HTTP_X_FORWARDED_PROTO]``), and a best-effort
    ``resolver_match``. The ``method`` defaults to ``POST`` for Socket.IO
    events but is overridable via ``router_data["method"]``.

    Args:
        router_data: Cookie/header/IP/path information for the synthetic request.

    Returns:
        A populated :class:`django.http.HttpRequest`.
    """
    from django.http import HttpRequest, QueryDict

    headers: dict[str, str] = dict(router_data.get("headers") or {})
    cookie_header = headers.get("cookie", "")
    client_ip = router_data.get("ip", "")
    path_raw = router_data.get("pathname", "/") or "/"
    if "?" in path_raw:
        path, _, qs_from_path = path_raw.partition("?")
    else:
        path = path_raw
        qs_from_path = ""

    method = str(router_data.get("method") or "POST").upper()

    get = QueryDict(mutable=True)
    if qs_from_path:
        get.update(QueryDict(qs_from_path))
    query = router_data.get("query")
    if isinstance(query, dict):
        for key, value in query.items():
            if value is not None:
                get[str(key)] = str(value)

    request = HttpRequest()
    request.method = method  # pyright: ignore[reportAttributeAccessIssue]
    request.path = path
    request.path_info = path
    request.GET = get  # pyright: ignore[reportAttributeAccessIssue]
    request._reflex_django_headers = headers  # noqa: SLF001 — for request.headers proxy

    from http.cookies import SimpleCookie

    cookie_jar: SimpleCookie = SimpleCookie()
    if cookie_header:
        try:
            cookie_jar.load(cookie_header)
        except Exception:
            cookie_jar = SimpleCookie()
    request.COOKIES = {key: morsel.value for key, morsel in cookie_jar.items()}

    host_header = headers.get("host", "") or headers.get("Host", "")
    server_name, server_port = _split_host_port(host_header)
    scheme = _scheme_from_headers(headers)

    request.META = {
        "REMOTE_ADDR": client_ip or "127.0.0.1",
        "PATH_INFO": path,
        "QUERY_STRING": get.urlencode(),
        "REQUEST_METHOD": method,
        "HTTP_COOKIE": cookie_header,
        "SERVER_NAME": server_name,
        "SERVER_PORT": server_port,
        "wsgi.url_scheme": scheme,
        "HTTP_X_FORWARDED_PROTO": scheme,
    }
    for name, value in headers.items():
        meta_key = "HTTP_" + name.upper().replace("-", "_")
        request.META.setdefault(meta_key, value)

    # Mirror Django's HttpRequest.scheme/_get_scheme behavior.
    request.META.setdefault("HTTP_HOST", host_header or f"{server_name}:{server_port}")

    _populate_post_from_payload(request, router_data)

    match = _resolve_url_match(path)
    if match is not None:
        request.resolver_match = match  # pyright: ignore[reportAttributeAccessIssue]

    return request


def _build_request_from_event(
    event: Event,
    state: BaseState | None = None,
) -> HttpRequest:
    """Build a Django HttpRequest from a Reflex event (and optional state).

    Args:
        event: The incoming Reflex event whose ``router_data`` carries
            cookie/header/IP information.
        state: Client state used to fall back when the event omits cookies
            (typical for upload handlers before the upload patch runs).

    Returns:
        A populated :class:`django.http.HttpRequest`.
    """
    router_data = _resolve_router_data(event, state)
    return _build_request_from_router_data(router_data)


def _attach_anonymous_user(request: HttpRequest) -> None:
    """Set ``request.user = AnonymousUser`` so middleware fallbacks are safe."""
    try:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        pass


async def _eagerly_resolve_lazy_user(request: HttpRequest) -> None:
    """Replace any :class:`~django.utils.functional.SimpleLazyObject` user with a real one.

    Django's :class:`~django.contrib.auth.middleware.AuthenticationMiddleware`
    sets ``request.user = SimpleLazyObject(lambda: get_user(request))``. The
    underlying ``get_user`` issues a synchronous database query against the
    session row, which raises :class:`~django.core.exceptions.SynchronousOnlyOperation`
    if our async event handler later does even ``request.user.is_authenticated``.

    We resolve the user eagerly with :func:`django.contrib.auth.aget_user` so
    every subsequent access in the Reflex event flow is plain attribute
    access on an :class:`~django.contrib.auth.models.AbstractBaseUser`
    instance. On failure (no session middleware, no auth app installed, etc.)
    we leave the request alone — the existing ``AnonymousUser`` fallback set
    by :func:`_attach_anonymous_user` keeps things working.
    """
    try:
        from django.contrib.auth import aget_user
        from django.utils.functional import SimpleLazyObject
    except ImportError:
        return

    user = getattr(request, "user", None)
    if user is None:
        return
    if not isinstance(user, SimpleLazyObject):
        return
    try:
        resolved = await aget_user(request)
    except Exception:
        return
    if resolved is not None:
        request.user = resolved  # pyright: ignore[reportAttributeAccessIssue]


async def _run_full_middleware_chain(
    request: HttpRequest,
) -> HttpResponse | None:
    """Run ``settings.MIDDLEWARE`` against the synthetic request.

    Returns the :class:`~django.http.HttpResponse` produced by the chain
    (either the terminal empty 200 or a short-circuit) or ``None`` when
    the middleware chain is disabled via
    ``REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN = False``.
    """
    from django.conf import settings

    if not getattr(settings, "REFLEX_DJANGO_RUN_MIDDLEWARE_CHAIN", True):
        return None

    from reflex_django.event_handler import run_middleware_chain

    try:
        return await run_middleware_chain(request)
    except Exception:
        from reflex_base.utils import console

        console.warn(
            "reflex-django event-bridge middleware chain raised; "
            "continuing without a middleware response."
        )
        return None


async def bridge_request_for_state(
    state: Any,
    event: Event | None = None,
) -> tuple[HttpRequest, HttpResponse | None] | None:
    """Build the synthetic request and run ``settings.MIDDLEWARE`` against it.

    Args:
        state: Reflex state used to recover ``router_data`` when the event omits it.
        event: The incoming Reflex event, or ``None`` to bridge from state only.

    Returns:
        ``(request, response)`` when bridging succeeds. ``response`` is the
        middleware-chain output, or ``None`` if the chain is disabled.
        Returns ``None`` when no usable ``router_data`` is available.
    """
    try:
        if event is not None:
            request = _build_request_from_event(event, state)
        else:
            router_data = _router_data_from_state_chain(state)
            if not router_data:
                return None
            request = _build_request_from_router_data(router_data)
    except Exception:
        return None

    # Default to AnonymousUser so middleware that touches ``request.user``
    # before AuthenticationMiddleware (e.g. custom request-logging) does not
    # ``AttributeError``.
    _attach_anonymous_user(request)

    response = await _run_full_middleware_chain(request)

    # Async-safety: ``AuthenticationMiddleware`` leaves a ``SimpleLazyObject``
    # in ``request.user`` that triggers a sync DB query on first access.
    # Resolve it now (in async context) so handlers can safely use
    # ``self.user`` / ``self.request.user`` without a SynchronousOnlyOperation.
    await _eagerly_resolve_lazy_user(request)

    try:
        await _attach_reflex_context(request)
    except Exception:
        pass

    return request, response


async def bind_django_request_for_handler_state(
    handler_state: Any,
    *,
    event: Event | None = None,
) -> None:
    """Ensure *handler_state* can use ``self.request`` in the current event."""
    from reflex_django.context import begin_event_request, current_request
    from reflex_django.state.request_binding import bind_request_on_state

    http = current_request()
    if http is None:
        root = handler_state
        try:
            root = handler_state._get_root_state()  # noqa: SLF001
        except (AttributeError, TypeError):
            pass
        bridged = await bridge_request_for_state(root, event)
        if bridged is not None:
            http, response = bridged
            begin_event_request(http)
            begin_event_response(response)
    bind_request_on_state(handler_state, http)


async def _attach_reflex_context(request: HttpRequest) -> None:
    """Run configured context processors and cache JSON-safe output on ``request``.

    Controlled by ``REFLEX_DJANGO_AUTO_LOAD_CONTEXT`` (default ``True``). When
    enabled, runs on every bridged event so handlers can use ``self.request`` /
    ``self.django_context`` without calling :meth:`~reflex_django.states.AppState.load_django_context`.
    """
    from django.conf import settings

    from reflex_django.context import set_request_reflex_context
    from reflex_django.reflex_context import (
        collect_reflex_context,
        reflex_context_processor_paths,
    )

    auto_load = getattr(settings, "REFLEX_DJANGO_AUTO_LOAD_CONTEXT", True)
    if not auto_load and not reflex_context_processor_paths():
        return
    merged = await collect_reflex_context(request)
    set_request_reflex_context(request, merged)


class DjangoEventBridge(Middleware):
    """Reflex event middleware that binds a Django request to each event.

    Install automatically by leaving
    :attr:`reflex_django.ReflexDjangoPlugin.install_event_bridge` set to
    ``True`` (the default). The bridge is a no-op when Django's auth/session
    apps are not installed.
    """

    def __init__(self) -> None:
        """Ensure Django is configured before any event is processed."""
        configure_django()
        from reflex_django.upload_patch import apply_upload_router_data_patch

        apply_upload_router_data_patch()

    async def preprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
    ) -> StateUpdate | None:
        """Bind a synthetic Django request + response to the current async task.

        Steps:

        1. Build a Django :class:`~django.http.HttpRequest` from
           ``event.router_data`` (cookies, headers, client IP, optional POST
           payload).
        2. Run ``settings.MIDDLEWARE`` (filtered by
           ``REFLEX_DJANGO_EVENT_MIDDLEWARE_SKIP``) against it through
           :class:`reflex_django.event_handler.EventMiddlewareHandler`. This is
           where ``SessionMiddleware``, ``AuthenticationMiddleware``,
           ``MessageMiddleware``, ``LocaleMiddleware``, ``MaintenanceMode``,
           and any custom middleware run for the event.
        3. Bind ``request`` and ``response`` to the per-task ContextVars and
           onto the state tree (so ``self.request`` / ``self.response`` work
           inside the handler).
        4. If the middleware chain short-circuited with a 3xx redirect and
           ``REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE`` is enabled,
           translate it into a Reflex :func:`reflex.redirect` and return
           that as the event result.

        Args:
            app: The Reflex application (unused).
            state: The client state; used to recover ``router_data`` when
                upload events omit cookies (see :func:`_resolve_router_data`).
            event: The incoming Reflex event.

        Returns:
            ``None`` to let the event run, or a Reflex
            :class:`~reflex.state.StateUpdate` that short-circuits the event
            with a redirect derived from the middleware response.
        """
        end_event_request()
        end_event_response()
        bridged = await bridge_request_for_state(state, event)
        if bridged is None:
            from reflex_base.utils import console

            console.warn(
                "reflex-django event bridge could not build Django request for this event"
            )
            return None
        request, response = bridged

        begin_event_request(request)
        begin_event_response(response)
        from reflex.state import BaseState as _BaseState
        from reflex_django.state.auth_bridge import maybe_sync_app_state_auth
        from reflex_django.state.request_binding import (
            bind_request_on_state,
            bind_request_on_state_tree,
            bind_response_on_state_tree,
        )

        if isinstance(state, _BaseState):
            bind_request_on_state_tree(state, request)
            bind_response_on_state_tree(state, response)
            try:
                handler_state = await state.get_state(event.state_cls)
                bind_request_on_state(handler_state, request)
            except Exception:
                pass
            user = getattr(request, "user", None)
            if getattr(user, "is_authenticated", False):
                session = getattr(request, "session", None)
                sk = getattr(session, "session_key", None) or ""
                if sk:
                    from reflex_django.session_js import (
                        mirror_auth_cookies_to_state_tree,
                    )

                    mirror_auth_cookies_to_state_tree(state, sk)
            await maybe_sync_app_state_auth(
                state,
                handler_state_cls=getattr(event, "state_cls", None),
            )
            from reflex_django.state.auth_bridge import maybe_sync_django_context_state

            await maybe_sync_django_context_state(
                state,
                handler_state_cls=getattr(event, "state_cls", None),
            )

        short_circuit = self._maybe_short_circuit_redirect(response)
        if short_circuit is not None:
            return short_circuit
        return None

    @staticmethod
    def _maybe_short_circuit_redirect(
        response: HttpResponse | None,
    ) -> StateUpdate | None:
        """Translate a 3xx middleware response into a Reflex redirect.

        Args:
            response: The middleware-chain response, possibly ``None``.

        Returns:
            A :class:`~reflex.state.StateUpdate` that issues
            :func:`reflex.redirect` to the response's ``Location``, or
            ``None`` when the response is missing, not a redirect, or
            auto-translation is disabled by
            ``REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE = False``.
        """
        if response is None:
            return None
        try:
            from django.conf import settings
        except Exception:
            return None
        if not getattr(
            settings,
            "REFLEX_DJANGO_AUTO_REDIRECT_FROM_MIDDLEWARE",
            True,
        ):
            return None

        status = getattr(response, "status_code", 200)
        if not (300 <= status < 400):
            return None
        location = response.get("Location") if hasattr(response, "get") else None
        if not location:
            return None

        try:
            import reflex as rx
            from reflex.state import StateUpdate
        except Exception:
            return None

        redirect_event = rx.redirect(location)
        return StateUpdate(delta={}, events=[redirect_event])

    async def postprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
        update: StateUpdate,
    ) -> StateUpdate:
        """Release the bound request/response after the event (when Reflex invokes this).

        Reflex's current event processor only runs ``preprocess``; we still
        clear stale bindings at the start of the next ``preprocess``. This
        hook keeps behavior correct if postprocessing is wired in later.

        Returns:
            The same ``update`` object passed in.
        """
        del app, state, event
        end_event_request()
        end_event_response()
        return update
