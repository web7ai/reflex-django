"""Router data resolution for synthetic Django requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.bridge.state_tree import find_in_parent_chain

if TYPE_CHECKING:
    from reflex_base.event import Event
    from reflex.state import BaseState
    from starlette.requests import Request


def _router_data_from_starlette_request(request: Request) -> dict[str, Any]:
    """Build ``router_data`` from a Starlette upload HTTP request."""
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
        router_data.get("pathname") or router_data.get("ip") or router_data.get("query")
    )


def _router_data_from_state_chain(state: Any) -> dict[str, Any]:
    """Return the nearest non-empty ``router_data`` on the state tree."""

    def _usable_router_data(node: Any) -> dict[str, Any] | None:
        raw = getattr(node, "router_data", None)
        if isinstance(raw, dict) and _router_data_is_usable(raw):
            return raw
        return None

    found = find_in_parent_chain(state, _usable_router_data)
    return found if found is not None else {}


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
    """Merge event and state ``router_data``, preferring event cookies when set."""
    raw_event_rd = getattr(event, "router_data", None)
    event_rd: dict[str, Any] = raw_event_rd if isinstance(raw_event_rd, dict) else {}
    if _router_data_is_usable(event_rd) and (event_rd.get("headers") or {}).get(
        "cookie"
    ):
        return event_rd

    state_rd = _router_data_from_state_chain(state)
    if _router_data_is_usable(state_rd):
        return _merge_router_data_with_state_cookie(state_rd, event_rd)

    if _router_data_is_usable(event_rd):
        return event_rd

    return state_rd


__all__ = [
    "_merge_router_data_with_state_cookie",
    "_resolve_router_data",
    "_router_data_from_starlette_request",
    "_router_data_from_state_chain",
    "_router_data_is_usable",
]
