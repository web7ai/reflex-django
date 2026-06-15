"""Tests for AppState page dispatch map and scoped auth sync."""

from __future__ import annotations

from unittest import mock

import pytest
import reflex as rx

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.runtime.app_factory import (  # noqa: E402
    prepare_pages_for_compile,
    reset_app_factory_cache,
)
from reflex_django.runtime.compile_validate import (  # noqa: E402
    expected_dispatch_keys_from_app,
    missing_frontend_dispatchers,
)
from reflex_django.pages.decorators import clear_page_registry, page
from reflex_django.mount.config import clear_mount_registration, register_mount
from reflex_django.state.auth_bridge import (  # noqa: E402
    _handler_state_class_chain,
    _sync_auth_snapshots_in_tree,
)
from reflex_django.states import AppState  # noqa: E402


class _HomeState(AppState):
    message: str = "guest"

    @rx.event
    async def on_load(self):
        self.message = "loaded"


@pytest.fixture(autouse=True)
def _reset() -> None:
    clear_mount_registration()
    register_mount(app_name="demo")
    reset_app_factory_cache()
    clear_page_registry()
    yield
    reset_app_factory_cache()
    clear_page_registry()
    clear_mount_registration()


@pytest.fixture(autouse=True)
def _mock_test_reflex_app(monkeypatch: pytest.MonkeyPatch) -> None:
    import reflex as rx

    app = rx.App()
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.load_native_reflex_app",
        lambda: app,
    )
    monkeypatch.setattr(
        "reflex_django.runtime.app_factory.load_app_factory",
        lambda: app,
    )


def test_handler_state_class_chain_includes_appstate_ancestors() -> None:
    chain = _handler_state_class_chain(_HomeState)
    names = [cls.__name__ for cls in chain]
    assert "DjangoUserState" in names or any(
        issubclass(c, AppState) for c in chain
    )
    assert chain[-1] is _HomeState


def test_expected_dispatch_keys_from_app_includes_home_state() -> None:
    from reflex.page import DECORATED_PAGES

    DECORATED_PAGES.clear()

    @page(route="/", on_load=_HomeState.on_load)
    def index() -> rx.Component:
        return rx.text(_HomeState.message)

    prepare_pages_for_compile()
    from reflex_django.runtime.app_factory import load_app_factory

    app = load_app_factory()
    keys = expected_dispatch_keys_from_app(app)
    assert any(_HomeState.get_full_name() in key or key.endswith(_HomeState.get_name()) for key in keys)


def test_missing_frontend_dispatchers_uses_app_tree_not_global_registry(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = tmp_path / "context.js"
    context.write_text(
        f'"{_HomeState.get_full_name()}": dispatch_home,',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "reflex.state.all_base_state_classes",
        {
            "reflex___state____state": None,
            "reflex___state____state.unused___auth___django_auth_state": None,
        },
    )

    @page(route="/")
    def index() -> rx.Component:
        return rx.text("x")

    prepare_pages_for_compile()
    from reflex_django.runtime.app_factory import load_app_factory

    app = load_app_factory()
    expected = expected_dispatch_keys_from_app(app)
    missing = missing_frontend_dispatchers(context, expected_keys=expected, app=app)
    assert "unused___auth___django_auth_state" not in missing


def test_ancestor_dispatch_keys_cover_handler_chain() -> None:
    from reflex_django.runtime.compile_validate import ancestor_dispatch_keys_for_handler

    keys = ancestor_dispatch_keys_for_handler(_HomeState)
    assert _HomeState.get_full_name() in keys
    assert len(keys) >= 2


def test_apply_auth_snapshot_for_event_handler_guest_user() -> None:
    import asyncio

    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpRequest

    from reflex_django.states.auth import apply_auth_snapshot_for_event_handler
    from reflex_django.bridge.context import begin_event_request, end_event_request

    handler = _HomeState()
    handler.inherited_vars = {"is_authenticated": None}
    handler.dirty_vars = set()
    handler.substates = {}

    http = HttpRequest()
    http.user = AnonymousUser()  # type: ignore[attr-defined]

    async def _run() -> None:
        end_event_request()
        begin_event_request(http)
        await apply_auth_snapshot_for_event_handler(handler)
        end_event_request()

    asyncio.run(_run())
    assert handler.is_authenticated is False


def test_apply_auth_snapshot_skips_unchanged_guest_snapshot() -> None:
    import asyncio

    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpRequest

    from reflex_django.states.auth import apply_auth_snapshot_for_event_handler
    from reflex_django.bridge.context import begin_event_request, end_event_request

    owner = mock.Mock()
    owner.user_id = None
    owner.username = ""
    owner.email = ""
    owner.first_name = ""
    owner.last_name = ""
    owner.is_authenticated = False
    owner.is_staff = False
    owner.is_superuser = False
    owner.group_names = []
    owner.inherited_vars = {}

    handler = mock.Mock()
    handler.inherited_vars = {"is_authenticated": mock.Mock()}
    handler.substates = {}

    http = HttpRequest()
    http.user = AnonymousUser()  # type: ignore[attr-defined]

    write_mock = mock.AsyncMock()
    dirty_mock = mock.Mock()

    async def _run() -> None:
        end_event_request()
        begin_event_request(http)
        with mock.patch(
            "reflex_django.states.auth._auth_snapshot_owner",
            return_value=owner,
        ), mock.patch(
            "reflex_django.states.auth._write_auth_snapshot_to_owner",
            write_mock,
        ), mock.patch(
            "reflex_django.states.auth._mark_auth_snapshot_dirty_subtree",
            dirty_mock,
        ):
            await apply_auth_snapshot_for_event_handler(handler)
        end_event_request()

    asyncio.run(_run())
    write_mock.assert_not_awaited()
    dirty_mock.assert_not_called()


def test_maybe_sync_skips_reflex_internal_on_load_state() -> None:
    import asyncio

    from reflex.state import OnLoadInternalState
    from reflex_django.state.auth_bridge import maybe_sync_app_state_auth

    root = mock.Mock()

    async def _run() -> None:
        await maybe_sync_app_state_auth(
            root,
            handler_state_cls=OnLoadInternalState,
        )

    with mock.patch(
        "reflex_django.state.auth_bridge._sync_auth_snapshots_in_tree",
        new=mock.AsyncMock(),
    ) as sync_mock:
        asyncio.run(_run())
        sync_mock.assert_not_awaited()


def test_sync_auth_snapshots_scoped_to_handler_branch() -> None:
    import asyncio

    root = mock.Mock()
    root._get_root_state.return_value = root
    root.get_state = mock.AsyncMock(return_value=mock.Mock())

    node = mock.Mock()
    node.inherited_vars = {}

    async def _run() -> None:
        with mock.patch(
            "reflex_django.state.auth_bridge._resolve_substate_node",
            return_value=node,
        ) as resolve_mock, mock.patch(
            "reflex_django.states.auth.apply_auth_snapshot_for_event_handler",
            new=mock.AsyncMock(),
        ) as apply_mock, mock.patch(
            "reflex_django.states.auth._mark_inherited_auth_snapshot_dirty",
        ) as dirty_mock:
            await _sync_auth_snapshots_in_tree(
                root,
                handler_state_cls=_HomeState,
            )

        apply_mock.assert_awaited_once()
        resolve_mock.assert_not_called()
        dirty_mock.assert_not_called()

    asyncio.run(_run())
