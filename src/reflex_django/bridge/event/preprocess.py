"""Django event bridge preprocess orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex.middleware import Middleware

from reflex_django.bridge.context import (
    begin_event_request,
    begin_event_response,
    clear_event_tier,
    end_event_request,
    end_event_response,
    set_event_tier,
)
from reflex_django.bridge.event.request_builder import (
    _attach_anonymous_user,
    _build_request_from_event,
    _build_request_from_router_data,
)
from reflex_django.bridge.event.router_data import _router_data_from_state_chain
from reflex_django.bridge.state_tree import resolve_state_root, unwrap_state_proxy
from reflex_django.setup.conf import configure_django

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from reflex.app import App
    from reflex.state import BaseState, StateUpdate
    from reflex_base.event import Event


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

        from reflex_django.core.debug import debug_log_exception

        debug_log_exception(f"middleware chain raised for tier {tier!r}")
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
        from reflex_django.core.debug import debug_log_exception

        debug_log_exception("failed to build synthetic Django request for event")
        return None

    _attach_anonymous_user(request)

    session_key = request.COOKIES.get("sessionid", "") or ""

    with measure_event_phase(f"middleware_{tier}"):
        response = None
        used_cache = False
        if tier == "auth_only":
            from reflex_django.bridge.auth_fast_path import try_apply_cached_auth

            used_cache = await try_apply_cached_auth(request, session_key)
        if not used_cache:
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
    root_state: Any | None = None,
) -> None:
    """Ensure *handler_state* can use ``self.request`` in the current event."""
    from reflex_django.bridge.context import (
        begin_event_request,
        current_event_tier,
        current_request,
    )
    from reflex_django.state.request_binding import bind_request_on_state

    http = current_request()
    if http is None:
        # Honour the tier the bridge middleware already resolved for this event.
        # Without this, ``smart``/``none`` modes silently fall back to ``full``
        # because the default ``tier`` argument here is ``"full"``.
        resolved_tier = current_event_tier()
        if resolved_tier is None:
            resolved_tier = tier
        if resolved_tier == "none":
            bind_request_on_state(handler_state, None)
            return
        bridge_state = (
            root_state
            or resolve_state_root(handler_state)
            or unwrap_state_proxy(handler_state)
        )
        bridged = await bridge_request_for_state(
            bridge_state, event, tier=resolved_tier
        )
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
        clear_event_tier()

        from reflex_django.bridge.tier import resolve_bridge_tier, tier_needs_auth_sync

        handler_state_cls = getattr(event, "state_cls", None)
        tier = resolve_bridge_tier(handler_state_cls, event)
        # Publish the resolved tier so the patched ``process_event`` hook
        # (``bind_django_request_for_handler_state``) does not rebuild a full
        # Django request for ``smart``/``none`` events.
        set_event_tier(tier)

        try:
            from reflex_django.devtools.inspector import (
                devtools_enabled,
                start_event_capture,
            )

            if devtools_enabled():
                start_event_capture(
                    tier=tier,
                    handler=getattr(event, "name", "") or "",
                )
        except Exception:
            from reflex_django.core.debug import debug_log_exception

            debug_log_exception("devtools start_event_capture failed")

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
            bind_request_on_state_branch,
            bind_response_on_state_branch,
        )

        if isinstance(state, _BaseState):
            handler_state = None
            try:
                handler_state = await state.get_state(event.state_cls)
            except Exception:
                from reflex_django.core.debug import debug_log_exception

                debug_log_exception(
                    "failed to resolve handler substate for request binding"
                )
                handler_state = None
            # Bind only on the handler substate branch (handler + ancestors)
            # rather than the entire state tree, which walks every unrelated
            # substate on each event.
            branch_target = handler_state if handler_state is not None else state
            bind_request_on_state_branch(branch_target, request)
            bind_response_on_state_branch(branch_target, response)
            if handler_state is not None:
                bind_request_on_state(handler_state, request)
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
        try:
            from reflex_django.devtools.inspector import (
                devtools_enabled,
                finish_event_capture,
            )

            if devtools_enabled():
                import logging

                record = finish_event_capture()
                if record is not None:
                    logging.getLogger("reflex_django.devtools").debug(
                        "event tier=%s handler=%s queries=%d duration_ms=%.2f",
                        record.tier,
                        record.handler,
                        record.query_count,
                        record.duration_ms,
                    )
        except Exception:
            from reflex_django.core.debug import debug_log_exception

            debug_log_exception("devtools finish_event_capture failed")
        end_event_request()
        end_event_response()
        clear_event_tier()
        return update


__all__ = [
    "DjangoEventBridge",
    "bind_django_request_for_handler_state",
    "bridge_request_for_state",
]
