"""Bridge Django auth/session middleware into Reflex's event flow."""

from reflex_django.bridge.event.preprocess import (
    DjangoEventBridge,
    bind_django_request_for_handler_state,
    bridge_request_for_state,
)
from reflex_django.bridge.event.request_builder import (
    _attach_anonymous_user,
    _build_request_from_event,
    _build_request_from_router_data,
    _populate_post_from_payload,
    _resolve_url_match,
    _scheme_from_headers,
    _split_host_port,
)
from reflex_django.bridge.event.router_data import (
    _merge_router_data_with_state_cookie,
    _resolve_router_data,
    _router_data_from_starlette_request,
    _router_data_from_state_chain,
    _router_data_is_usable,
)

__all__ = [
    "DjangoEventBridge",
    "bind_django_request_for_handler_state",
    "bridge_request_for_state",
    "_attach_anonymous_user",
    "_build_request_from_event",
    "_build_request_from_router_data",
    "_merge_router_data_with_state_cookie",
    "_populate_post_from_payload",
    "_resolve_router_data",
    "_resolve_url_match",
    "_router_data_from_starlette_request",
    "_router_data_from_state_chain",
    "_router_data_is_usable",
    "_scheme_from_headers",
    "_split_host_port",
]