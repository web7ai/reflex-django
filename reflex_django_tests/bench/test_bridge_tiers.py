"""Lightweight benchmarks for bridge tier middleware invocation counts."""

from __future__ import annotations

from typing import Any, cast
from unittest import mock

from django.test import override_settings

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.bridge.django_event import DjangoEventBridge  # noqa: E402


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


@override_settings(REFLEX_DJANGO_EVENT_CACHE_TTL=0)
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

        with override_settings(REFLEX_DJANGO_EVENT_BRIDGE_MODE=mode), mock.patch(
            "reflex_django.bridge.django_event.bridge_request_for_state",
            side_effect=_counting_bridge,
        ), mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
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