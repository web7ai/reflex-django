"""Lightweight benchmarks for bridge tier middleware invocation counts."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from django.test import override_settings

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.bridge.event import DjangoEventBridge  # noqa: E402


class _StubEvent:
    def __init__(
        self,
        *,
        state_cls: type | None = None,
        name: str = "app.state.click",
    ) -> None:
        self.router_data = {"headers": {}, "ip": "", "pathname": "/"}
        self.name = name
        self.state_cls = state_cls


@override_settings(RX_EVENT_CACHE_TTL=0)
def test_smart_mode_invokes_bridge_fewer_times_than_full() -> None:
    import reflex as rx

    from reflex_django.states import AppState

    class UiState(rx.State):
        pass

    class CartState(AppState):
        pass

    bridge = DjangoEventBridge()

    async def _record_bridge(*args, **kwargs):  # noqa: ANN002, ANN003
        return mock.Mock(), None

    async def _run_mode(mode: str, events: list[_StubEvent]) -> int:
        calls = 0

        async def _counting_bridge(*args, **kwargs):  # noqa: ANN002, ANN003
            nonlocal calls
            calls += 1
            return mock.Mock(), None

        with (
            override_settings(RX_EVENT_BRIDGE_MODE=mode),
            mock.patch(
                "reflex_django.bridge.event.preprocess.bridge_request_for_state",
                side_effect=_counting_bridge,
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
        ):
            for event in events:
                await bridge.preprocess(
                    app=mock.Mock(),
                    state=mock.Mock(),
                    event=cast(Any, event),
                )
        return calls

    import asyncio

    events = [
        _StubEvent(state_cls=UiState),
        _StubEvent(state_cls=UiState),
        _StubEvent(state_cls=CartState),
    ]

    full_calls = asyncio.run(_run_mode("full", events))
    smart_calls = asyncio.run(_run_mode("smart", events))

    assert full_calls == 3
    assert smart_calls == 1


@override_settings(RX_EVENT_CACHE_TTL=0)
def test_smart_mode_end_to_end_skips_middleware_via_process_event() -> None:
    """End-to-end: preprocess + the patched process_event hook together.

    The earlier bench only measured ``preprocess``; this exercises the full
    event path so the F1 regression (process_event rebuilding a full request)
    would fail this test.
    """
    import reflex as rx

    from reflex_django.states import AppState
    from reflex_django.bridge.event.preprocess import (
        bind_django_request_for_handler_state,
    )

    class UiState(rx.State):
        pass

    class CartState(AppState):
        pass

    bridge = DjangoEventBridge()

    async def _run_mode(mode: str, events: list[_StubEvent]) -> int:
        calls = 0

        async def _counting_bridge(*args, **kwargs):  # noqa: ANN002, ANN003
            nonlocal calls
            calls += 1
            return mock.Mock(), None

        with (
            override_settings(RX_EVENT_BRIDGE_MODE=mode),
            mock.patch(
                "reflex_django.bridge.event.preprocess.bridge_request_for_state",
                side_effect=_counting_bridge,
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
        ):
            for event in events:
                await bridge.preprocess(
                    app=mock.Mock(),
                    state=mock.Mock(spec=["get_state"]),
                    event=cast(Any, event),
                )
                # Simulate the patched process_event hook running next.
                await bind_django_request_for_handler_state(mock.Mock())
                await bridge.postprocess(
                    app=mock.Mock(),
                    state=mock.Mock(),
                    event=cast(Any, event),
                    update=mock.Mock(),
                )
        return calls

    import asyncio

    events = [
        _StubEvent(state_cls=UiState),
        _StubEvent(state_cls=UiState),
        _StubEvent(state_cls=CartState),
    ]

    full_calls = asyncio.run(_run_mode("full", events))
    smart_calls = asyncio.run(_run_mode("smart", events))

    assert full_calls == 3
    # 2 UI events skipped entirely, only the AppState event bridges.
    assert smart_calls == 1
