"""Bind Django request context and filter event deltas."""

from __future__ import annotations

from typing import Any


def _patch_process_event() -> None:
    """Bind ``self.request`` on the handler substate before each event runs."""
    try:
        import reflex_base.event.processor.base_state_processor as bsp
    except ImportError:
        return

    if getattr(bsp, "_reflex_django_process_event_patched", False):
        return

    original = bsp.process_event

    async def process_event(handler, payload, state, root_state):  # noqa: ANN001
        from reflex_django.bridge.event import bind_django_request_for_handler_state

        await bind_django_request_for_handler_state(
            state,
            root_state=root_state,
        )
        await original(handler, payload, state, root_state)

    bsp.process_event = process_event
    bsp._reflex_django_process_event_patched = True
    bsp._reflex_django_process_event_original = original


def _patch_basestate_getstate() -> None:
    """Strip non-picklable Django wrappers from state before Reflex pickles it.

    The Django-outer event bridge attaches per-request artefacts on each Reflex
    state instance via :mod:`reflex_django.state.request_binding`:

    - ``_rx_request_wrapper`` — :class:`~reflex_django.state.request.DjangoStateRequest`
      holding the live :class:`~django.http.HttpRequest` (and an authenticated
      :class:`~django.contrib.auth.models.User`, the URL ``ResolverMatch``,
      Django messages, etc.).
    - ``_rx_response`` — the :class:`~django.http.HttpResponse`
      produced by ``settings.MIDDLEWARE``.

    Reflex serializes state to Redis/in-memory between events using
    :mod:`dill`. The Django user, the resolver match (which captures view
    functions and url-patterns), and the response object are all
    non-picklable in the general case and surface as
    :class:`reflex.utils.exceptions.StateSerializationError`. The bridge
    re-attaches these on every event from context vars, so dropping them
    before pickling is safe.
    """
    try:
        from reflex.state import BaseState
    except ImportError:
        return

    if getattr(BaseState, "_reflex_django_getstate_patched", False):
        return

    original_getstate = BaseState.__getstate__

    def patched_getstate(self: Any) -> dict[str, Any]:
        state = original_getstate(self)
        if not isinstance(state, dict):
            return state
        for transient in _DJANGO_TRANSIENT_STATE_ATTRS:
            state.pop(transient, None)
        return state

    BaseState.__getstate__ = patched_getstate  # type: ignore[method-assign]
    BaseState._reflex_django_getstate_patched = True
    BaseState._reflex_django_getstate_original = original_getstate


def _patch_event_context_emit_delta() -> None:
    """Filter emitted deltas to substates present in ``.web/utils/context.js``."""
    try:
        from reflex_base.event.context import EventContext
    except ImportError:
        return

    if getattr(EventContext, "_reflex_django_emit_delta_patched", False):
        return

    original_emit_delta = EventContext.emit_delta

    async def emit_delta(
        self: Any,
        delta: Any,
    ) -> None:
        from reflex_django.runtime.compile_validate import filter_delta_to_compiled_dispatch_keys

        if not delta:
            return
        filtered = filter_delta_to_compiled_dispatch_keys(dict(delta))
        if not filtered:
            return
        await original_emit_delta(self, filtered)

    EventContext.emit_delta = emit_delta  # type: ignore[method-assign]
    EventContext._reflex_django_emit_delta_patched = True
    EventContext._reflex_django_emit_delta_original = original_emit_delta
