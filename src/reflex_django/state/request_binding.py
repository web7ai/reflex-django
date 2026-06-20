"""Attach the bridged Django request/response to Reflex state instances for handlers."""

from __future__ import annotations

from typing import Any

from reflex_django.bridge.context import (
    current_request,
    current_response,
)
from reflex_django.bridge.state_tree import unwrap_state_proxy
from reflex_django.state.request import DjangoStateRequest

REQUEST_WRAPPER_ATTR = "_rx_request_wrapper"
RESPONSE_ATTR = "_rx_response"


def _binding_target(state: Any) -> Any:
    """Return the real state instance when *state* is a Reflex background proxy."""
    return unwrap_state_proxy(state)


def bind_request_on_state(
    state: Any,
    http_request: Any | None = None,
    http_response: Any | None = None,
) -> None:
    """Store :class:`~reflex_django.state.request.DjangoStateRequest` on *state*.

    Reflex runs :meth:`~reflex_django.bridge.event.DjangoEventBridge.preprocess` on
    the root state, then resolves the handler substate (e.g. ``HomeState``) in
    :func:`reflex_base.event.processor.base_state_processor.process_event`.
    Context variables alone are not always visible on that substate instance;
    binding on the handler state makes ``self.request`` reliable.

    Args:
        state: The :class:`~reflex.state.State` (or substate) about to run a handler.
        http_request: Optional explicit request; defaults to :func:`current_request`.
        http_response: Optional explicit response; defaults to :func:`current_response`.
    """
    target = _binding_target(state)
    http = http_request if http_request is not None else current_request()
    response = http_response if http_response is not None else current_response()
    if http is None:
        try:
            object.__delattr__(target, REQUEST_WRAPPER_ATTR)
        except AttributeError:
            pass
        try:
            object.__delattr__(target, RESPONSE_ATTR)
        except AttributeError:
            pass
        return
    wrapper = DjangoStateRequest(
        http,
        response=response,
    )
    object.__setattr__(target, REQUEST_WRAPPER_ATTR, wrapper)
    if response is not None:
        object.__setattr__(target, RESPONSE_ATTR, response)
    else:
        try:
            object.__delattr__(target, RESPONSE_ATTR)
        except AttributeError:
            pass


def clear_request_on_state(state: Any) -> None:
    """Remove previously bound request and response wrappers from *state*."""
    target = _binding_target(state)
    for attr in (REQUEST_WRAPPER_ATTR, RESPONSE_ATTR):
        try:
            object.__delattr__(target, attr)
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


def bind_request_on_state_branch(
    node: Any,
    http_request: Any | None = None,
) -> None:
    """Bind the active request on *node* and its ancestors only.

    Unlike :func:`bind_request_on_state_tree`, this walks *up* the parent chain
    (the handler substate branch) instead of every descendant. It avoids the
    per-event cost of touching unrelated substates while still making
    ``self.request`` available on the handler and any parent whose computed
    vars read the request.
    """
    http = http_request if http_request is not None else current_request()
    response = current_response()
    cur = node
    while cur is not None:
        bind_request_on_state(cur, http, response)
        cur = getattr(cur, "parent_state", None)


def bind_response_on_state_branch(
    node: Any,
    http_response: Any | None = None,
) -> None:
    """Refresh the bound response on *node* and its ancestors only."""
    http = current_request()
    response = http_response if http_response is not None else current_response()
    cur = node
    while cur is not None:
        bind_request_on_state(cur, http, response)
        cur = getattr(cur, "parent_state", None)


__all__ = [
    "REQUEST_WRAPPER_ATTR",
    "RESPONSE_ATTR",
    "bind_request_on_state",
    "bind_request_on_state_branch",
    "bind_request_on_state_tree",
    "bind_response_on_state_branch",
    "bind_response_on_state_tree",
    "clear_request_on_state",
]
