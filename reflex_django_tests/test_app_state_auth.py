"""Tests for unified auth on :class:`~reflex_django.states.AppState`."""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any, cast
from unittest import mock

import pytest

from reflex_django.conf import configure_django

configure_django()

from django.contrib.auth.models import User  # noqa: E402

from reflex_django.context import current_session  # noqa: E402
from reflex_django.middleware import DjangoEventBridge  # noqa: E402
from reflex_django.state.auth_bridge import SessionProxy  # noqa: E402
from reflex_django.states import AppState  # noqa: E402


class _StubEvent:
    def __init__(self, router_data: dict[str, Any] | None = None) -> None:
        self.router_data = router_data or {}


def _run_in_fresh_context(coro_factory):
    async def _wrapped():
        return await coro_factory()

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped)


class _DashboardState(AppState):
    pass


def test_ac1_app_state_user_property_reflects_authenticated_user() -> None:
    state = _DashboardState()
    user = User(username="alice", email="alice@example.com")
    user.is_authenticated = True  # type: ignore[attr-defined]

    with mock.patch("reflex_django.state.auth_bridge.current_user", return_value=user):
        assert state.user.username == "alice"
        assert state.user.email == "alice@example.com"
        assert state.user.is_authenticated is True


def test_app_state_request_user_matches_user_property() -> None:
    state = _DashboardState()
    user = mock.Mock()
    user.username = "bob"
    user.email = "bob@example.com"
    user.is_authenticated = True
    http_request = mock.Mock()
    http_request.user = user

    with mock.patch(
        "reflex_django.state.auth_bridge.current_request",
        return_value=http_request,
    ), mock.patch(
        "reflex_django.context.current_request",
        return_value=http_request,
    ):
        assert state.request.user.username == "bob"
        assert state.request.user is state.user
        assert state.django_request is http_request


def test_ac2_session_write_persists_across_events() -> None:
    bridge = DjangoEventBridge()
    state = _DashboardState()
    event = _StubEvent(router_data={"headers": {}, "ip": "127.0.0.1", "pathname": "/"})

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=state, event=cast(Any, event)
            )
        state.session["theme"] = "dark"
        session_key = current_session().session_key
        assert session_key

        event2 = _StubEvent(
            router_data={
                "headers": {"cookie": f"sessionid={session_key}"},
                "ip": "127.0.0.1",
                "pathname": "/",
            }
        )
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=state, event=cast(Any, event2)
            )
        assert state.session["theme"] == "dark"

    _run_in_fresh_context(_go)


def test_session_proxy_raises_without_bound_session() -> None:
    proxy = SessionProxy(None)
    with pytest.raises(RuntimeError):
        _ = proxy["missing"]


def test_ac5_auto_sync_refreshes_app_state_snapshot() -> None:
    from reflex_django.state.auth_bridge import maybe_sync_app_state_auth

    state = _DashboardState()
    user = User(username="bob")
    user.is_authenticated = True  # type: ignore[attr-defined]

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.current_user",
            return_value=user,
        ):
            await maybe_sync_app_state_auth(state)
        assert state.is_authenticated is True
        assert state.username == "bob"

    _run_in_fresh_context(_go)


def test_login_returns_false_when_no_request() -> None:
    state = _DashboardState()

    async def _go() -> None:
        with mock.patch("reflex_django.state.auth_bridge.current_request", return_value=None):
            ok = await state.login("u", "p")
        assert ok is False

    _run_in_fresh_context(_go)


def test_has_perm_delegates_to_shortcut() -> None:
    state = _DashboardState()
    user = mock.Mock()
    user.is_authenticated = True

    async def _go() -> None:
        with mock.patch("reflex_django.state.auth_bridge.current_user", return_value=user):
            with mock.patch(
                "reflex_django.state.auth_bridge.auser_has_perm",
                new=mock.AsyncMock(return_value=True),
            ) as hp:
                assert await state.has_perm("app.change_model") is True
                hp.assert_awaited_once_with(user, "app.change_model")

    _run_in_fresh_context(_go)


def test_has_group_uses_snapshot_when_loaded() -> None:
    state = _DashboardState()
    state.group_names = ["admins"]
    user = mock.Mock()
    user.is_authenticated = True

    async def _go() -> None:
        with mock.patch("reflex_django.state.auth_bridge.current_user", return_value=user):
            assert await state.has_group("admins") is True
            assert await state.has_group("other") is False

    _run_in_fresh_context(_go)


def test_app_state_inherits_django_user_state_and_model_crud() -> None:
    from reflex_django.auth_state import DjangoUserState
    from reflex_django.state import ModelCRUDView

    class _Notes(AppState, ModelCRUDView):
        pass

    assert issubclass(_Notes, AppState)
    assert issubclass(_Notes, DjangoUserState)


def test_app_state_injects_setters_for_manual_form_vars() -> None:
    class _ProfileState(AppState):
        display_name: str = ""
        email: str = ""
        bio: str = ""

    assert hasattr(_ProfileState, "set_display_name")
    assert hasattr(_ProfileState, "set_email")
    assert hasattr(_ProfileState, "set_bio")
