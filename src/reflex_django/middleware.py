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
from reflex_django.context import begin_event_request, end_event_request

if TYPE_CHECKING:
    from django.http import HttpRequest
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


def _router_data_from_state_chain(state: Any) -> dict[str, Any]:
    """Return the nearest ``router_data`` with a session cookie on the state tree.

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
        if isinstance(raw, dict) and (raw.get("headers") or {}).get("cookie"):
            return raw
        parent = getattr(node, "parent_state", None)
        if parent is None or isinstance(parent, Mock):
            break
        node = parent
    return {}


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
    if (event_rd.get("headers") or {}).get("cookie"):
        return event_rd

    state_rd = _router_data_from_state_chain(state)
    if (state_rd.get("headers") or {}).get("cookie"):
        return {**state_rd, **event_rd}

    return event_rd


def _build_request_from_router_data(router_data: dict[str, Any]) -> HttpRequest:
    """Build a Django HttpRequest from Reflex ``router_data``.

    Args:
        router_data: Cookie/header/IP/path information for the synthetic request.

    Returns:
        A populated :class:`django.http.HttpRequest`.
    """
    from django.http import HttpRequest

    headers: dict[str, str] = dict(router_data.get("headers") or {})
    cookie_header = headers.get("cookie", "")
    client_ip = router_data.get("ip", "")
    path_raw = router_data.get("pathname", "/") or "/"
    if "?" in path_raw:
        path, _, qs_from_path = path_raw.partition("?")
    else:
        path = path_raw
        qs_from_path = ""

    from django.http import QueryDict

    get = QueryDict(mutable=True)
    if qs_from_path:
        get.update(QueryDict(qs_from_path))
    query = router_data.get("query")
    if isinstance(query, dict):
        for key, value in query.items():
            if value is not None:
                get[str(key)] = str(value)

    request = HttpRequest()
    request.method = "GET"  # pyright: ignore[reportAttributeAccessIssue]
    request.path = path
    request.path_info = path
    request.GET = get  # pyright: ignore[reportAttributeAccessIssue]
    request._reflex_django_headers = headers  # noqa: SLF001 — for request.headers proxy

    # Translate the cookie header into request.COOKIES the way Django does
    # for HTTP requests.
    from http.cookies import SimpleCookie

    cookie_jar: SimpleCookie = SimpleCookie()
    if cookie_header:
        try:
            cookie_jar.load(cookie_header)
        except Exception:
            cookie_jar = SimpleCookie()
    request.COOKIES = {key: morsel.value for key, morsel in cookie_jar.items()}

    # Populate META with the headers Django code typically inspects.
    request.META = {
        "REMOTE_ADDR": client_ip or "127.0.0.1",
        "PATH_INFO": path,
        "QUERY_STRING": get.urlencode(),
        "REQUEST_METHOD": "GET",
        "HTTP_COOKIE": cookie_header,
    }
    for name, value in headers.items():
        meta_key = "HTTP_" + name.upper().replace("-", "_")
        request.META.setdefault(meta_key, value)

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


def _attach_session(request: HttpRequest) -> None:
    """Load the Django session from ``request.COOKIES`` onto ``request.session``.

    Args:
        request: The synthetic request to mutate.
    """
    from importlib import import_module

    from django.conf import settings
    from django.contrib.sessions.backends.base import SessionBase

    engine = import_module(settings.SESSION_ENGINE)
    cookie_name = getattr(settings, "SESSION_COOKIE_NAME", "sessionid")
    session_key = request.COOKIES.get(cookie_name)
    session: SessionBase = engine.SessionStore(session_key)
    request.session = session  # pyright: ignore[reportAttributeAccessIssue]


def _activate_i18n_for_request(request: HttpRequest) -> None:
    """Run Django locale negotiation and ``translation.activate`` on ``request``.

    Mirrors :meth:`django.middleware.locale.LocaleMiddleware.process_request`
    so Reflex event handlers see the same active language as Django HTTP.

    Args:
        request: Synthetic request with ``session`` and ``META`` already set.
    """
    from django.conf import settings

    if not getattr(settings, "USE_I18N", False):
        return
    if not getattr(settings, "REFLEX_DJANGO_I18N_EVENT_BRIDGE", True):
        return
    try:
        from django.middleware.locale import LocaleMiddleware

        LocaleMiddleware(lambda _req: None).process_request(request)
    except Exception:
        return


async def _attach_user(request: HttpRequest) -> None:
    """Populate ``request.user`` from the request session (auth backend).

    Resolves the user via :func:`django.contrib.auth.aget_user` (the async
    variant). The sync ``get_user`` does the same work but hits Django's
    sync ORM on every authenticated session load, which raises
    :class:`SynchronousOnlyOperation` from inside Reflex's event loop and
    would silently fall back to ``AnonymousUser``.

    Args:
        request: The synthetic request to mutate. Must already have
            ``request.session`` set by :func:`_attach_session`.
    """
    try:
        from django.contrib.auth import aget_user
    except ImportError:
        return

    try:
        request.user = await aget_user(  # pyright: ignore[reportAttributeAccessIssue]
            request
        )
    except Exception:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()  # pyright: ignore[reportAttributeAccessIssue]


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
        """Bind a synthetic Django request to the current async task.

        Args:
            app: The Reflex application (unused).
            state: The client state; used to recover ``router_data`` when upload
                events omit cookies (see :func:`_resolve_router_data`).
            event: The incoming Reflex event whose ``router_data`` carries the
                cookie/header/IP information needed to rebuild a Django
                request.

        Returns:
            Always ``None`` — the bridge never short-circuits the event.
        """
        end_event_request()
        try:
            request = _build_request_from_event(event, state)
            _attach_session(request)
            _activate_i18n_for_request(request)
            await _attach_user(request)
        except Exception:
            return None

        begin_event_request(request)
        from reflex.state import BaseState as _BaseState
        from reflex_django.state.auth_bridge import maybe_sync_app_state_auth

        if isinstance(state, _BaseState):
            await maybe_sync_app_state_auth(state)
        return None

    async def postprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
        update: StateUpdate,
    ) -> StateUpdate:
        """Release the bound request after the event (when Reflex invokes this).

        Reflex's current event processor only runs ``preprocess``; we still
        clear stale bindings at the start of the next ``preprocess``. This
        hook keeps behavior correct if postprocessing is wired in later.

        Returns:
            The same ``update`` object passed in.
        """
        del app, state, event
        end_event_request()
        return update
