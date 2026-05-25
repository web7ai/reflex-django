"""Attach the bridged Django request/response to Reflex state instances for handlers."""

from __future__ import annotations

from typing import Any

from reflex_django.context import (
    current_request,
    current_response,
    get_request_reflex_context,
)
from reflex_django.state.request import DjangoStateRequest

REQUEST_WRAPPER_ATTR = "_django_led_request_wrapper"
RESPONSE_ATTR = "_django_led_response"


def bind_request_on_state(
    state: Any,
    http_request: Any | None = None,
    http_response: Any | None = None,
) -> None:
    """Store :class:`~reflex_django.state.request.DjangoStateRequest` on *state*.

    Reflex runs :meth:`~reflex_django.middleware.DjangoEventBridge.preprocess` on
    the root state, then resolves the handler substate (e.g. ``HomeState``) in
    :func:`reflex_base.event.processor.base_state_processor.process_event`.
    Context variables alone are not always visible on that substate instance;
    binding on the handler state makes ``self.request`` reliable.

    Args:
        state: The :class:`~reflex.state.State` (or substate) about to run a handler.
        http_request: Optional explicit request; defaults to :func:`current_request`.
        http_response: Optional explicit response; defaults to :func:`current_response`.
    """
    http = http_request if http_request is not None else current_request()
    response = http_response if http_response is not None else current_response()
    if http is None:
        try:
            object.__delattr__(state, REQUEST_WRAPPER_ATTR)
        except AttributeError:
            pass
        try:
            object.__delattr__(state, RESPONSE_ATTR)
        except AttributeError:
            pass
        return
    wrapper = DjangoStateRequest(
        http,
        get_request_reflex_context(http),
        response=response,
    )
    object.__setattr__(state, REQUEST_WRAPPER_ATTR, wrapper)
    if response is not None:
        object.__setattr__(state, RESPONSE_ATTR, response)
    else:
        try:
            object.__delattr__(state, RESPONSE_ATTR)
        except AttributeError:
            pass


def clear_request_on_state(state: Any) -> None:
    """Remove previously bound request and response wrappers from *state*."""
    for attr in (REQUEST_WRAPPER_ATTR, RESPONSE_ATTR):
        try:
            object.__delattr__(state, attr)
        except AttributeError:
            pass


def bind_request_on_state_tree(
    root_state: Any,
    http_request: Any | None = None,
) -> None:
    """Bind the active request on *root_state* and every descendant substate instance."""
    http = http_request if http_request is not None else current_request()
    response = current_response()

    def visit(node: Any) -> None:
        bind_request_on_state(node, http, response)
        for child in (getattr(node, "substates", None) or {}).values():
            visit(child)

    visit(root_state)


def bind_response_on_state_tree(
    root_state: Any,
    http_response: Any | None = None,
) -> None:
    """Refresh the bound response on *root_state* and every descendant substate.

    Useful when the response is produced after the initial request bind, e.g.
    if a custom flow calls :func:`bind_request_on_state_tree` first and runs
    middleware later.
    """
    http = current_request()
    response = http_response if http_response is not None else current_response()

    def visit(node: Any) -> None:
        bind_request_on_state(node, http, response)
        for child in (getattr(node, "substates", None) or {}).values():
            visit(child)

    visit(root_state)


__all__ = [
    "REQUEST_WRAPPER_ATTR",
    "RESPONSE_ATTR",
    "bind_request_on_state",
    "bind_request_on_state_tree",
    "bind_response_on_state_tree",
    "clear_request_on_state",
]
