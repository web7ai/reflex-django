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

from typing import TYPE_CHECKING

from reflex.middleware import Middleware
from reflex_django.conf import configure_django
from reflex_django.context import begin_event_request, end_event_request

if TYPE_CHECKING:
    from django.http import HttpRequest
    from reflex_base.event import Event

    from reflex.app import App
    from reflex.state import BaseState, StateUpdate


def _build_request_from_event(event: Event) -> HttpRequest:
    """Build a Django HttpRequest from a Reflex event's router data.

    Args:
        event: The incoming Reflex event whose ``router_data`` carries
            cookie/header/IP information.

    Returns:
        A populated :class:`django.http.HttpRequest`.
    """
    from django.http import HttpRequest

    router_data = getattr(event, "router_data", None) or {}
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

    async def preprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
    ) -> StateUpdate | None:
        """Bind a synthetic Django request to the current async task.

        Args:
            app: The Reflex application (unused).
            state: The client state (unused; bridge does not mutate state).
            event: The incoming Reflex event whose ``router_data`` carries the
                cookie/header/IP information needed to rebuild a Django
                request.

        Returns:
            Always ``None`` — the bridge never short-circuits the event.
        """
        end_event_request()
        try:
            request = _build_request_from_event(event)
            _attach_session(request)
            _activate_i18n_for_request(request)
            await _attach_user(request)
        except Exception:
            return None

        begin_event_request(request)
        from reflex_django.state.auth_bridge import maybe_sync_app_state_auth

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
