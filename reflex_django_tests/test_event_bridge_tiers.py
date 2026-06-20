"""Tests for tiered event bridge resolution and behavior."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from django.test import override_settings

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.bridge.event import DjangoEventBridge  # noqa: E402
from reflex_django.bridge.registry import reset_bridge_resolver_cache  # noqa: E402
from reflex_django.bridge.tier import resolve_bridge_tier  # noqa: E402


class _StubEvent:
    def __init__(
        self,
        router_data: dict[str, Any] | None = None,
        *,
        name: str = "app.state.click",
        state_cls: type | None = None,
    ) -> None:
        self.router_data = router_data or {}
        self.name = name
        self.state_cls = state_cls


def test_resolve_bridge_tier_defaults_to_full() -> None:
    assert resolve_bridge_tier(None, _StubEvent()) == "full"


@override_settings(RX_EVENT_BRIDGE_MODE="smart")
def test_smart_mode_skips_plain_rx_state() -> None:
    import reflex as rx

    class FilterState(rx.State):
        pass

    assert resolve_bridge_tier(FilterState, _StubEvent()) == "none"


@override_settings(RX_EVENT_BRIDGE_MODE="smart")
def test_smart_mode_uses_full_for_app_state() -> None:
    from reflex_django.states import AppState

    class CartState(AppState):
        pass

    assert resolve_bridge_tier(CartState, _StubEvent()) == "full"


@override_settings(RX_EVENT_BRIDGE_MODE="smart")
def test_per_class_override_wins_over_smart_mode() -> None:
    import reflex as rx

    class HotState(rx.State):
        _rx_bridge = "full"

    assert resolve_bridge_tier(HotState, _StubEvent()) == "full"


@override_settings(RX_EVENT_BRIDGE_MODE="smart")
def test_upload_event_requires_auth_only_minimum() -> None:
    import reflex as rx

    class FilterState(rx.State):
        _rx_bridge = "none"

    event = _StubEvent(
        router_data={"pathname": "/_upload"},
        name="app.state.handle_upload",
    )
    assert resolve_bridge_tier(FilterState, event) == "auth_only"


def test_custom_resolver_has_highest_precedence() -> None:
    import reflex as rx

    def custom_resolver(handler_state_cls, event):  # noqa: ANN001, ARG001
        return "none"

    class NeedsFull(rx.State):
        _rx_bridge = "full"

    with mock.patch(
        "reflex_django.bridge.registry._load_custom_resolver",
        return_value=custom_resolver,
    ):
        assert resolve_bridge_tier(NeedsFull, _StubEvent()) == "none"
    reset_bridge_resolver_cache()


@override_settings(RX_EVENT_BRIDGE_MODE="smart", RX_EVENT_CACHE_TTL=0)
def test_preprocess_skips_middleware_for_none_tier() -> None:
    import reflex as rx

    class FilterState(rx.State):
        pass

    bridge = DjangoEventBridge()
    event = _StubEvent(state_cls=FilterState)

    async def _go() -> None:
        with mock.patch(
            "reflex_django.bridge.event.preprocess.bridge_request_for_state",
            new=mock.AsyncMock(),
        ) as bridge_call:
            result = await bridge.preprocess(
                app=mock.Mock(),
                state=mock.Mock(),
                event=cast(Any, event),
            )
            assert result is None
            bridge_call.assert_not_awaited()

    import asyncio

    asyncio.run(_go())


@override_settings(RX_EVENT_BRIDGE_MODE="smart", RX_EVENT_CACHE_TTL=0)
def test_preprocess_runs_bridge_for_app_state_in_smart_mode() -> None:
    from reflex_django.states import AppState

    class CartState(AppState):
        pass

    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={"headers": {}, "ip": "", "pathname": "/"},
        state_cls=CartState,
    )

    async def _go() -> None:
        with (
            mock.patch(
                "reflex_django.bridge.event.preprocess.bridge_request_for_state",
                new=mock.AsyncMock(return_value=(mock.Mock(), None)),
            ) as bridge_call,
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
        ):
            await bridge.preprocess(
                app=mock.Mock(),
                state=mock.Mock(spec=["get_state"]),
                event=cast(Any, event),
            )
            bridge_call.assert_awaited_once()
            assert bridge_call.await_args.kwargs["tier"] == "full"

    import asyncio

    asyncio.run(_go())


@override_settings(RX_EVENT_BRIDGE_MODE="smart", RX_EVENT_CACHE_TTL=0)
def test_process_event_honours_none_tier_in_smart_mode() -> None:
    """Regression for F1: preprocess + patched process_event must not run the
    full middleware chain for plain ``rx.State`` handlers in smart mode.

    Before the fix, ``bind_django_request_for_handler_state`` defaulted to
    ``tier="full"`` and rebuilt a full Django request even though preprocess
    had resolved ``none``.
    """
    import reflex as rx

    from reflex_django.bridge.context import current_event_tier
    from reflex_django.bridge.event.preprocess import (
        bind_django_request_for_handler_state,
    )

    class FilterState(rx.State):
        pass

    bridge = DjangoEventBridge()
    event = _StubEvent(state_cls=FilterState)

    async def _go() -> None:
        with mock.patch(
            "reflex_django.bridge.event.preprocess.bridge_request_for_state",
            new=mock.AsyncMock(return_value=(mock.Mock(), None)),
        ) as bridge_call:
            # 1. Bridge middleware resolves and publishes the "none" tier.
            await bridge.preprocess(
                app=mock.Mock(),
                state=mock.Mock(),
                event=cast(Any, event),
            )
            assert current_event_tier() == "none"
            # 2. The patched process_event hook runs next in the same context.
            await bind_django_request_for_handler_state(mock.Mock())
            bridge_call.assert_not_awaited()

    import asyncio

    asyncio.run(_go())


@override_settings(RX_EVENT_BRIDGE_MODE="full", RX_EVENT_CACHE_TTL=0)
def test_bind_handler_state_uses_resolved_tier_without_preprocess() -> None:
    """Without preprocess, the binding falls back to the default tier."""
    import reflex as rx

    from reflex_django.bridge.context import clear_event_tier
    from reflex_django.bridge.event.preprocess import (
        bind_django_request_for_handler_state,
    )

    class FilterState(rx.State):
        pass

    async def _go() -> None:
        clear_event_tier()
        with mock.patch(
            "reflex_django.bridge.event.preprocess.bridge_request_for_state",
            new=mock.AsyncMock(return_value=(mock.Mock(), None)),
        ) as bridge_call:
            await bind_django_request_for_handler_state(mock.Mock())
            bridge_call.assert_awaited_once()
            assert bridge_call.await_args.kwargs["tier"] == "full"

    import asyncio

    asyncio.run(_go())
