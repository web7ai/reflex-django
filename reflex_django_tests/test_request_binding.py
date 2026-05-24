"""Tests for binding Django request onto handler substates."""

from __future__ import annotations

import asyncio
import contextvars
from unittest import mock

from reflex_django.conf import configure_django

configure_django()

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.http import HttpRequest  # noqa: E402

from reflex_django.context import begin_event_request, end_event_request  # noqa: E402
from reflex_django.state.request_binding import (  # noqa: E402
    REQUEST_WRAPPER_ATTR,
    bind_request_on_state,
)
from reflex_django.states import AppState  # noqa: E402


class HomeState(AppState):
    pass


def test_bind_request_on_state_attaches_wrapper() -> None:
    http = HttpRequest()
    http.user = AnonymousUser()  # type: ignore[attr-defined]
    http.method = "GET"
    http.path = "/"

    state = mock.Mock(spec=HomeState)

    async def _go() -> None:
        end_event_request()
        begin_event_request(http)
        bind_request_on_state(state, http)
        assert object.__getattribute__(state, REQUEST_WRAPPER_ATTR).user.is_authenticated is False
        end_event_request()

    ctx = contextvars.copy_context()
    ctx.run(asyncio.run, _go())


def test_preprocess_binds_handler_substate() -> None:
    from reflex_django.middleware import DjangoEventBridge

    bridge = DjangoEventBridge()
    child = HomeState()
    root = HomeState()

    class _StubEvent:
        router_data = {
            "headers": {"cookie": ""},
            "ip": "127.0.0.1",
            "pathname": "/",
        }
        state_cls = HomeState

    with mock.patch(
        "reflex_django.state.request_binding.bind_request_on_state_tree",
    ), mock.patch(
        "reflex_django.state.request_binding.bind_request_on_state",
    ) as bind_mock, mock.patch(
        "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
        new=mock.AsyncMock(),
    ), mock.patch(
        "reflex_django.state.auth_bridge.maybe_sync_django_context_state",
        new=mock.AsyncMock(),
    ), mock.patch.object(
        HomeState,
        "get_state",
        new=mock.AsyncMock(return_value=child),
    ) as get_state_mock:
        async def _go() -> None:
            end_event_request()
            await bridge.preprocess(app=mock.Mock(), state=root, event=_StubEvent())
            end_event_request()

        ctx = contextvars.copy_context()
        ctx.run(asyncio.run, _go())

    get_state_mock.assert_awaited_once_with(HomeState)
    bind_mock.assert_any_call(child, mock.ANY)


def test_bind_django_request_for_handler_state_without_preprocess() -> None:
    from reflex_django.middleware import bind_django_request_for_handler_state

    state = HomeState()
    rd = {
        "headers": {"cookie": ""},
        "ip": "127.0.0.1",
        "pathname": "/",
    }
    state.router_data = rd  # type: ignore[attr-defined]

    async def _go() -> None:
        end_event_request()
        await bind_django_request_for_handler_state(state)
        assert state.request.user.is_authenticated is False
        end_event_request()

    ctx = contextvars.copy_context()
    ctx.run(asyncio.run, _go())


def test_process_event_is_patched_after_integration_install() -> None:
    from reflex_django.integration import install_reflex_django_integration

    install_reflex_django_integration()

    import reflex_base.event.processor.base_state_processor as bsp

    assert getattr(bsp, "_reflex_django_process_event_patched", False) is True
