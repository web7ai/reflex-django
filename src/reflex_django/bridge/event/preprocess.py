"""Django event bridge preprocess orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex.middleware import Middleware
from reflex_django.setup.conf import configure_django
from reflex_django.bridge.context import (
    begin_event_request,
    begin_event_response,
    end_event_request,
    end_event_response,
)
from reflex_django.bridge.event.request_builder import (
    _attach_anonymous_user,
    _build_request_from_event,
    _build_request_from_router_data,
)
from reflex_django.bridge.event.router_data import _router_data_from_state_chain
from reflex_django.bridge.state_tree import resolve_state_root

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from reflex_base.event import Event

    from reflex.app import App
    from reflex.state import BaseState, StateUpdate


async def _eagerly_resolve_lazy_user(request: HttpRequest) -> None:
    """Replace lazy ``request.user`` with an eagerly resolved instance."""
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


async def _run_middleware_for_tier(
    request: HttpRequest,
    tier: str,
) -> HttpResponse | None:
    """Run middleware for *tier* (``full`` or ``auth_only``)."""
    from django.conf import settings

    if tier not in {"full", "auth_only"}:
        return None
    if not getattr(settings, "RX_RUN_MIDDLEWARE_CHAIN", True):
        return None

    from reflex_django.bridge.event_handler import (
        run_auth_middleware_chain,
        run_middleware_chain,
    )

    try:
        if tier == "auth_only":
            return await run_auth_middleware_chain(request)
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
    *,
    tier: str = "full",
) -> tuple[HttpRequest, HttpResponse | None] | None:
    """Build the synthetic request and run middleware for *tier*."""
    from reflex_django.bridge.cache import set_cached_event_context
    from reflex_django.bridge.metrics import measure_event_phase

    if tier == "none":
        return None

    try:
        with measure_event_phase("build_request"):
            if event is not None:
                request = _build_request_from_event(event, state)
            else:
                router_data = _router_data_from_state_chain(state)
                if not router_data:
                    return None
                request = _build_request_from_router_data(router_data)
    except Exception:
        return None

    _attach_anonymous_user(request)

    session_key = request.COOKIES.get("sessionid", "") or ""

    with measure_event_phase(f"middleware_{tier}"):
        response = await _run_middleware_for_tier(request, tier)

    with measure_event_phase("resolve_user"):
        await _eagerly_resolve_lazy_user(request)

    if session_key:
        set_cached_event_context(session_key, request)

    return request, response


async def bind_django_request_for_handler_state(
    handler_state: Any,
    *,
    event: Event | None = None,
    tier: str = "full",
) -> None:
    """Ensure *handler_state* can use ``self.request`` in the current event."""
    from reflex_django.bridge.context import begin_event_request, current_request
    from reflex_django.state.request_binding import bind_request_on_state

    http = current_request()
    if http is None:
        root = resolve_state_root(handler_state) or handler_state
        bridged = await bridge_request_for_state(root, event, tier=tier)
        if bridged is not None:
            http, response = bridged
            begin_event_request(http)
            begin_event_response(response)
    bind_request_on_state(handler_state, http)


class DjangoEventBridge(Middleware):
    """Reflex event middleware that binds a Django request to each event.

    Install automatically via
    :func:`reflex_django.runtime.integration.install_reflex_django_integration`
    (called during ``reflex run``). The bridge is a no-op when Django's
    auth/session apps are not installed.
    """

    def __init__(self) -> None:
        """Ensure Django is configured before any event is processed."""
        configure_django()
        from reflex_django.bridge.upload import apply_upload_router_data_patch

        apply_upload_router_data_patch()

    async def preprocess(
        self,
        app: App,
        state: BaseState,
        event: Event,
    ) -> StateUpdate | None:
        """Bind a synthetic Django request + response to the current async task."""
        end_event_request()
        end_event_response()

        from reflex_django.bridge.tier import resolve_bridge_tier, tier_needs_auth_sync

        handler_state_cls = getattr(event, "state_cls", None)
        tier = resolve_bridge_tier(handler_state_cls, event)
        if tier == "none":
            return None

        bridged = await bridge_request_for_state(state, event, tier=tier)
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
                    from reflex_django.bridge.session_js import (
                        mirror_auth_cookies_to_state_tree,
                    )

                    mirror_auth_cookies_to_state_tree(state, sk)
            if tier_needs_auth_sync(tier, handler_state_cls):
                await maybe_sync_app_state_auth(
                    state,
                    handler_state_cls=handler_state_cls,
                )

        short_circuit = self._maybe_short_circuit_redirect(response)
        if short_circuit is not None:
            return short_circuit
        return None

    @staticmethod
    def _maybe_short_circuit_redirect(
        response: HttpResponse | None,
    ) -> StateUpdate | None:
        """Translate a 3xx middleware response into a Reflex redirect."""
        if response is None:
            return None
        try:
            from django.conf import settings
        except Exception:
            return None
        if not getattr(
            settings,
            "RX_AUTO_REDIRECT_FROM_MIDDLEWARE",
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
        """Release the bound request/response after the event."""
        del app, state, event
        end_event_request()
        end_event_response()
        return update


__all__ = [
    "DjangoEventBridge",
    "bind_django_request_for_handler_state",
    "bridge_request_for_state",
]