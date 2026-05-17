"""Tests for upload handler auth via DjangoEventBridge and upload patch."""

from __future__ import annotations

import contextvars
from typing import Any, cast
from unittest import mock

from starlette.requests import Request

from reflex_django.conf import configure_django

configure_django()

from reflex_django.context import current_request, current_user  # noqa: E402
from reflex_django.middleware import (  # noqa: E402
    DjangoEventBridge,
    _resolve_router_data,
    _router_data_from_starlette_request,
    _router_data_from_state_chain,
)
from reflex_django.upload_patch import (  # noqa: E402
    apply_upload_router_data_patch,
    inject_router_data_into_event,
)


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
    import asyncio

    async def _wrapped():
        return await coro_factory()

    ctx = contextvars.copy_context()
    return ctx.run(asyncio.run, _wrapped())


def _make_starlette_request(
    *,
    cookie: str = "",
    path: str = "/_upload",
    client_host: str = "10.0.0.1",
    query_string: bytes = b"tab=1",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string,
        "headers": headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_router_data_from_starlette_request() -> None:
    request = _make_starlette_request(
        cookie="sessionid=abc123; csrftoken=zzz",
        path="/profile",
        client_host="192.168.1.5",
    )
    rd = _router_data_from_starlette_request(request)
    assert rd["headers"]["cookie"] == "sessionid=abc123; csrftoken=zzz"
    assert rd["ip"] == "192.168.1.5"
    assert rd["pathname"] == "/profile"
    assert rd["query"].get("tab") == "1"


def test_resolve_router_data_prefers_event_cookies() -> None:
    event = _StubEvent(
        router_data={"headers": {"cookie": "sessionid=event"}}
    )
    state = _StubState(
        router_data={"headers": {"cookie": "sessionid=state"}, "pathname": "/old"}
    )
    merged = _resolve_router_data(cast(Any, event), cast(Any, state))
    assert merged["headers"]["cookie"] == "sessionid=event"


def test_resolve_router_data_falls_back_to_root_state_chain() -> None:
    root = _StubState(
        router_data={
            "headers": {"cookie": "sessionid=root"},
            "ip": "1.2.3.4",
        }
    )
    profile = _StubState(router_data={"pathname": "/upload"}, parent_state=root)
    event = _StubEvent(router_data={"pathname": "/upload"})
    merged = _resolve_router_data(cast(Any, event), cast(Any, profile))
    assert merged["headers"]["cookie"] == "sessionid=root"
    assert merged["pathname"] == "/upload"
    assert _router_data_from_state_chain(profile)["headers"]["cookie"] == "sessionid=root"


def test_resolve_router_data_falls_back_to_state() -> None:
    event = _StubEvent(router_data={"pathname": "/upload"})
    state = _StubState(
        router_data={
            "headers": {"cookie": "sessionid=fromstate"},
            "ip": "1.2.3.4",
        }
    )
    merged = _resolve_router_data(cast(Any, event), cast(Any, state))
    assert merged["headers"]["cookie"] == "sessionid=fromstate"
    assert merged["pathname"] == "/upload"


def test_preprocess_upload_substate_uses_root_router_data() -> None:
    bridge = DjangoEventBridge()
    root = _StubState(
        router_data={
            "headers": {"cookie": "sessionid=rootcookie"},
            "ip": "8.8.8.8",
            "pathname": "/app",
        }
    )
    profile = _StubState(router_data={}, parent_state=root)
    event = _StubEvent(router_data={})

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=cast(Any, profile), event=cast(Any, event)
            )
        req = current_request()
        assert req is not None
        assert req.COOKIES.get("sessionid") == "rootcookie"

    _run_in_fresh_context(_go)


def test_preprocess_upload_event_uses_state_router_data_fallback() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={})
    state = _StubState(
        router_data={
            "headers": {"cookie": "sessionid=notreal"},
            "ip": "9.9.9.9",
            "pathname": "/dashboard",
        }
    )

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=cast(Any, state), event=cast(Any, event)
            )
        req = current_request()
        assert req is not None
        assert req.COOKIES.get("sessionid") == "notreal"
        assert req.META["REMOTE_ADDR"] == "9.9.9.9"
        assert req.path == "/dashboard"

    _run_in_fresh_context(_go)


def test_preprocess_upload_event_with_injected_router_data() -> None:
    bridge = DjangoEventBridge()
    event = _StubEvent(
        router_data={
            "headers": {"cookie": "sessionid=uploadcookie"},
            "ip": "5.6.7.8",
            "pathname": "/_upload",
        }
    )

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(), state=mock.Mock(), event=cast(Any, event)
            )
        req = current_request()
        assert req is not None
        assert req.COOKIES["sessionid"] == "uploadcookie"
        assert req.META["REMOTE_ADDR"] == "5.6.7.8"

    _run_in_fresh_context(_go)


def test_inject_router_data_into_event() -> None:
    from reflex_base.event import Event

    rd = {
        "headers": {"cookie": "sessionid=patched"},
        "ip": "1.1.1.1",
        "pathname": "/_upload",
    }
    event = Event(name="app.state.handle_upload", payload={"files": []})
    patched = inject_router_data_into_event(event, rd)
    assert patched.router_data["headers"]["cookie"] == "sessionid=patched"
    assert patched.router_data["ip"] == "1.1.1.1"


def test_apply_upload_router_data_patch_is_idempotent() -> None:
    import reflex_components_core.core._upload as upload_mod

    apply_upload_router_data_patch()
    first = upload_mod._upload_buffered_file
    apply_upload_router_data_patch()
    assert upload_mod._upload_buffered_file is first
    assert hasattr(upload_mod, "_upload_buffered_file__orig__")


def test_login_required_upload_handler_no_redirect_after_bridge() -> None:
    from django.contrib.auth.models import AnonymousUser

    from reflex_django.auth.decorators import login_required

    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={})
    state = _StubState(
        router_data={
            "headers": {"cookie": "sessionid=abc"},
            "ip": "127.0.0.1",
            "pathname": "/profile",
        }
    )

    class _ProfileState:
        @login_required(login_url="/login")
        async def handle_upload(self, files: list[Any] | None = None):
            return "saved"

    async def _go() -> None:
        auth_user = mock.Mock()
        auth_user.is_authenticated = True

        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ), mock.patch(
            "django.contrib.auth.aget_user",
            new=mock.AsyncMock(return_value=auth_user),
        ):
            await bridge.preprocess(
                app=mock.Mock(),
                state=cast(Any, state),
                event=cast(Any, event),
            )
            assert current_user() is auth_user
            out = await _ProfileState().handle_upload(files=[])
            assert out == "saved"

        # Without session cookies, same handler redirects.
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ), mock.patch(
            "django.contrib.auth.aget_user",
            new=mock.AsyncMock(return_value=AnonymousUser()),
        ):
            await bridge.preprocess(
                app=mock.Mock(),
                state=cast(Any, _StubState()),
                event=cast(Any, _StubEvent(router_data={})),
            )
            from reflex_base.event import EventSpec

            redirect = await _ProfileState().handle_upload(files=[])
            assert isinstance(redirect, EventSpec)

    _run_in_fresh_context(_go)


def test_login_required_upload_redirects_when_anonymous() -> None:
    from reflex_django.auth.decorators import login_required
    from reflex_base.event import EventSpec

    bridge = DjangoEventBridge()
    event = _StubEvent(router_data={})
    state = _StubState()

    class _ProfileState:
        @login_required(login_url="/login")
        async def handle_upload(self):
            return "saved"

    async def _go() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge.maybe_sync_app_state_auth",
            new=mock.AsyncMock(),
        ):
            await bridge.preprocess(
                app=mock.Mock(),
                state=cast(Any, state),
                event=cast(Any, event),
            )
        out = await _ProfileState().handle_upload()
        assert isinstance(out, EventSpec)

    _run_in_fresh_context(_go)
