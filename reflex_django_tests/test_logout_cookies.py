"""Tests for logout session/cookie clearing."""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any, cast
from unittest import mock

from reflex_django.setup.conf import configure_django

configure_django()

from django.http import HttpRequest  # noqa: E402

from reflex_django.bridge.event import DjangoEventBridge  # noqa: E402
from reflex_django.bridge.event import (  # noqa: E402
    _build_request_from_router_data,
    _resolve_router_data,
)
from reflex_django.bridge.session_js import (  # noqa: E402
    browser_auth_cookies_clear_js,
    browser_auth_logout_clear_js,
    browser_client_storage_clear_js,
    browser_reflex_token_clear_js,
    browser_session_storage_clear_js,
    clear_auth_cookies_from_state_tree,
    merge_session_cookie_into_router_data,
    mirror_auth_cookies_to_state_tree,
    strip_auth_cookies_from_cookie_header,
    strip_auth_cookies_from_request,
    strip_auth_cookies_from_router_data,
)
from reflex_django.states import AppState  # noqa: E402


class _StubEvent:
    def __init__(self, router_data: dict[str, Any] | None = None) -> None:
        self.router_data = router_data or {}


class _StubState:
    def __init__(
        self,
        router_data: dict[str, Any] | None = None,
        *,
        parent_state: Any = None,
    ) -> None:
        self.router_data = router_data or {}
        self.parent_state = parent_state

    def _get_root_state(self) -> _StubState:
        node: _StubState = self
        while node.parent_state is not None:
            node = node.parent_state
        return node


def _run_in_fresh_context(coro_factory):
    async def _wrapped():
        return await coro_factory()

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped())


def test_strip_auth_cookies_from_cookie_header() -> None:
    header = "sessionid=abc; csrftoken=zzz; theme=dark"
    stripped = strip_auth_cookies_from_cookie_header(header)
    assert stripped == "theme=dark"


def test_strip_auth_cookies_from_router_data() -> None:
    rd = {
        "headers": {"cookie": "sessionid=old; other=1"},
        "pathname": "/",
    }
    out = strip_auth_cookies_from_router_data(rd)
    assert out["headers"]["cookie"] == "other=1"


def test_clear_auth_cookies_from_state_tree() -> None:
    root = _StubState(
        router_data={"headers": {"cookie": "sessionid=root; x=1"}, "pathname": "/"}
    )
    child = _StubState(
        router_data={"headers": {"cookie": "sessionid=child"}, "pathname": "/x"},
        parent_state=root,
    )
    root.substates = {"child": child}
    clear_auth_cookies_from_state_tree(child)
    assert root.router_data["headers"]["cookie"] == "x=1"
    assert child.router_data["headers"]["cookie"] == ""


def test_browser_auth_cookies_clear_js_includes_session_and_csrf() -> None:
    js = browser_auth_cookies_clear_js()
    assert "sessionid" in js
    assert "csrftoken" in js
    assert "max-age=0" in js
    assert "document.cookie" in js


def test_session_cookie_clear_js_uses_multiple_expire_attempts() -> None:
    from reflex_django.bridge.session_js import session_cookie_clear_js

    js = session_cookie_clear_js()
    assert js.count("max-age=0") >= 2
    assert "document.cookie" in js


def test_browser_reflex_token_clear_js() -> None:
    js = browser_reflex_token_clear_js()
    assert "sessionStorage.removeItem('token')" in js
    assert "sessionStorage.clear()" not in js


def test_browser_session_storage_clear_js() -> None:
    js = browser_session_storage_clear_js()
    assert "sessionStorage.removeItem('token')" in js
    assert "sessionStorage.clear()" not in js


def test_browser_client_storage_clear_js() -> None:
    js = browser_client_storage_clear_js()
    assert "sessionStorage.removeItem('token')" in js
    assert "localStorage.clear()" in js


def test_browser_auth_logout_clear_js_includes_cookies_and_storage() -> None:
    js = browser_auth_logout_clear_js()
    assert "sessionid" in js
    assert "sessionStorage.removeItem('token')" in js
    assert "localStorage.clear()" not in js
    assert "sessionStorage.clear()" not in js


def test_logout_strips_request_cookies_after_alogout() -> None:
    bridge = DjangoEventBridge()
    state = AppState()
    event = _StubEvent(
        router_data={
            "headers": {
                "cookie": "sessionid=abc; csrftoken=csrf123",
            },
            "ip": "127.0.0.1",
            "pathname": "/",
        }
    )

    async def _go() -> None:
        with (
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.alogout",
                new=mock.AsyncMock(),
            ) as alogout_mock,
            mock.patch(
                "reflex_django.state.auth_bridge.session_async_save",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.states.auth.apply_auth_snapshot_to_state",
                new=mock.AsyncMock(),
            ),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=state, event=cast(Any, event)
            )
            request = state.request
            state.router_data = dict(event.router_data)

            await state.logout()

            alogout_mock.assert_awaited_once()
            assert "sessionid" not in request.COOKIES
            assert "csrftoken" not in request.COOKIES
            assert "sessionid" not in (request.META.get("HTTP_COOKIE") or "")
            assert "sessionid" not in state.router_data.get("headers", {}).get(
                "cookie", ""
            )

    _run_in_fresh_context(_go)


def test_logout_preserves_configured_session_keys() -> None:
    bridge = DjangoEventBridge()
    state = AppState()
    event = _StubEvent(
        router_data={
            "headers": {"cookie": "sessionid=abc"},
            "ip": "127.0.0.1",
            "pathname": "/",
        }
    )

    async def _go() -> None:
        async def _alogout_side_effect(request: Any) -> None:
            for key in list(request.session.keys()):
                del request.session[key]

        with (
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.alogout",
                new=mock.AsyncMock(side_effect=_alogout_side_effect),
            ) as alogout_mock,
            mock.patch(
                "reflex_django.state.auth_bridge.session_async_save",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.states.auth.apply_auth_snapshot_to_state",
                new=mock.AsyncMock(),
            ),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=state, event=cast(Any, event)
            )
            request = state.request
            request.session["theme"] = "dark"
            request.session["secret"] = "wipe-me"

            await state.logout()

            alogout_mock.assert_awaited_once()
            assert request.session.get("theme") == "dark"
            assert "secret" not in request.session

    _run_in_fresh_context(_go)


def test_strip_auth_cookies_from_request() -> None:
    request = HttpRequest()
    request.COOKIES = {"sessionid": "x", "csrftoken": "y", "other": "z"}
    request.META = {"HTTP_COOKIE": "sessionid=x; csrftoken=y; other=z"}
    strip_auth_cookies_from_request(request)
    assert request.COOKIES == {"other": "z"}
    assert request.META["HTTP_COOKIE"] == "other=z"


def test_merge_session_cookie_into_router_data() -> None:
    rd = {
        "headers": {"cookie": "sessionid=old; csrftoken=zzz; theme=dark"},
        "pathname": "/",
    }
    out = merge_session_cookie_into_router_data(rd, "newkey123")
    cookie = out["headers"]["cookie"]
    assert "sessionid=newkey123" in cookie
    assert "sessionid=old" not in cookie
    assert "csrftoken" not in cookie
    assert "theme=dark" in cookie


def test_mirror_auth_cookies_to_state_tree() -> None:
    root = _StubState(
        router_data={"headers": {"cookie": "sessionid=root; x=1"}, "pathname": "/"}
    )
    child = _StubState(
        router_data={"headers": {"cookie": ""}, "pathname": "/x"},
        parent_state=root,
    )
    root.substates = {"child": child}
    mirror_auth_cookies_to_state_tree(child, "after_login")
    assert "sessionid=after_login" in root.router_data["headers"]["cookie"]
    assert "x=1" in root.router_data["headers"]["cookie"]
    assert "sessionid=after_login" in child.router_data["headers"]["cookie"]


def test_resolve_router_data_finds_session_after_login_mirror() -> None:
    root = _StubState(
        router_data={
            "headers": {"cookie": "theme=dark"},
            "pathname": "/",
            "ip": "127.0.0.1",
        }
    )
    mirror_auth_cookies_to_state_tree(root, "mirrored_session")
    event = _StubEvent(router_data={"pathname": "/", "headers": {}, "ip": "127.0.0.1"})
    merged = _resolve_router_data(cast(Any, event), cast(Any, root))
    request = _build_request_from_router_data(merged)
    assert request.COOKIES.get("sessionid") == "mirrored_session"
    assert request.COOKIES.get("theme") == "dark"


def test_login_strips_stale_auth_cookies_before_alogin() -> None:
    bridge = DjangoEventBridge()
    state = AppState()
    event = _StubEvent(
        router_data={
            "headers": {"cookie": "sessionid=stale; csrftoken=oldcsrf"},
            "ip": "127.0.0.1",
            "pathname": "/login",
        }
    )

    async def _go() -> None:
        with (
            mock.patch(
                "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.aauthenticate_login_fields",
                new=mock.AsyncMock(return_value=mock.Mock(is_authenticated=True)),
            ),
            mock.patch(
                "reflex_django.state.auth_bridge.alogin",
                new=mock.AsyncMock(),
            ) as alogin_mock,
            mock.patch(
                "reflex_django.state.auth_bridge.session_async_save",
                new=mock.AsyncMock(),
            ),
            mock.patch(
                "reflex_django.states.auth.apply_auth_snapshot_to_state",
                new=mock.AsyncMock(),
            ),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=state, event=cast(Any, event)
            )
            request = state.request
            state.router_data = dict(event.router_data)
            request.session["stale"] = "value"

            ok = await state.login("user", "pass")

            assert ok is True
            alogin_mock.assert_awaited_once()
            assert "sessionid" not in request.COOKIES
            assert "csrftoken" not in request.COOKIES
            assert "stale" not in request.session
            assert "sessionid" not in state.router_data.get("headers", {}).get(
                "cookie", ""
            )

    _run_in_fresh_context(_go)
