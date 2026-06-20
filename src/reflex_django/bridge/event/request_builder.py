"""Build synthetic HttpRequest objects from Reflex events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.bridge.event.router_data import _resolve_router_data

if TYPE_CHECKING:
    from django.http import HttpRequest
    from reflex_base.event import Event
    from reflex.state import BaseState


def _split_host_port(host_header: str) -> tuple[str, str]:
    """Return ``(server_name, server_port)`` parsed from a ``Host:`` header."""
    if not host_header:
        return ("localhost", "80")
    host = host_header.strip()
    if host.startswith("["):
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
    proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto") or ""
    if proto:
        return str(proto).strip().lower().split(",")[0]
    return "http"


def _resolve_url_match(path: str) -> Any | None:
    """Best-effort URL resolution for the synthetic event request."""
    try:
        from django.conf import settings

        if not getattr(settings, "RX_EVENT_RESOLVE_URL", True):
            return None
    except Exception:
        pass
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
    """Optionally feed event payload kwargs into ``request.POST``."""
    try:
        from django.conf import settings
    except Exception:
        return
    if not getattr(settings, "RX_EVENT_POST_FROM_PAYLOAD", False):
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
    """Build a fully-populated Django HttpRequest from Reflex ``router_data``."""
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
    request._read_started = False  # noqa: SLF001
    request._body = b""  # noqa: SLF001
    request.method = method  # pyright: ignore[reportAttributeAccessIssue]
    request.path = path
    request.path_info = path
    request.GET = get  # pyright: ignore[reportAttributeAccessIssue]
    request._reflex_django_headers = headers  # noqa: SLF001

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
    """Build a Django HttpRequest from a Reflex event (and optional state)."""
    router_data = _resolve_router_data(event, state)
    return _build_request_from_router_data(router_data)


def _attach_anonymous_user(request: HttpRequest) -> None:
    """Set ``request.user = AnonymousUser`` so middleware fallbacks are safe."""
    try:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()  # pyright: ignore[reportAttributeAccessIssue]
    except Exception:
        pass


__all__ = [
    "_attach_anonymous_user",
    "_build_request_from_event",
    "_build_request_from_router_data",
    "_populate_post_from_payload",
    "_resolve_url_match",
    "_scheme_from_headers",
    "_split_host_port",
]
