"""Django auth/session bridge for :class:`~reflex_django.states.AppState`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx
from asgiref.sync import sync_to_async
from django.contrib.auth import alogin, alogout

from reflex_django.auth.login_fields import (
    DEFAULT_LOGIN_FIELDS,
    aauthenticate_login_fields,
)
from reflex_django.auth.shortcuts import auser_has_perm
from reflex_django.context import current_request, current_session, current_user

if TYPE_CHECKING:
    from django.contrib.sessions.backends.base import SessionBase


async def session_async_save(request: Any) -> None:
    """Persist the session row after mutating it in an async Reflex handler."""
    session = getattr(request, "session", None)
    if session is None:
        return
    asave = getattr(session, "asave", None)
    if callable(asave):
        await asave()
        return
    session.save()


class SessionProxy:
    """Proxy for :func:`current_session` with dict-like access and persistence."""

    __slots__ = ("_session",)

    def __init__(self, session: SessionBase | None) -> None:
        self._session = session

    def _require_session(self) -> SessionBase:
        if self._session is None:
            msg = "No Django session is bound to the current Reflex event."
            raise RuntimeError(msg)
        return self._session

    def __getitem__(self, key: str) -> Any:
        return self._require_session()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        session = self._require_session()
        session[key] = value
        session.save()

    def __delitem__(self, key: str) -> None:
        session = self._require_session()
        del session[key]
        session.save()

    def get(self, key: str, default: Any = None) -> Any:
        session = self._session
        if session is None:
            return default
        return session.get(key, default)

    async def asave(self) -> None:
        """Persist session changes (async-safe)."""
        request = current_request()
        if request is not None:
            await session_async_save(request)
        elif self._session is not None:
            asave = getattr(self._session, "asave", None)
            if callable(asave):
                await asave()
            else:
                self._session.save()

    def save(self) -> None:
        """Persist session changes synchronously."""
        self._require_session().save()


def _session_proxy() -> SessionProxy:
    return SessionProxy(current_session())


class AuthBridgeMixin:
    """Django user/session access and auth helpers for Reflex state handlers.

    Mixed into :class:`~reflex_django.states.AppState`. Use ``self.request``,
    ``self.user``, and ``self.session`` in event handlers (for example
    ``self.request.user``); use ``self.is_authenticated``, ``self.username``,
    etc. in UI (Reflex vars, synced via the event bridge).
    """

    @property
    def request(self) -> Any:
        """Bridged Django request for the current event (``self.request.user``, etc.)."""
        from reflex_django.state.request import DjangoStateRequest

        return DjangoStateRequest(current_request())

    @property
    def django_request(self) -> Any | None:
        """Raw :class:`django.http.HttpRequest` for the current event."""
        return current_request()

    @property
    def user(self) -> Any:
        """Live Django user for the current event (not a Reflex var)."""
        return current_user()

    @property
    def session(self) -> SessionProxy:
        """Django session for the current event with auto-save on mutation."""
        return _session_proxy()

    async def has_perm(self, perm: str) -> bool:
        """Whether ``self.user`` has the given Django permission."""
        return await auser_has_perm(self.user, perm)

    async def has_group(self, name: str) -> bool:
        """Whether ``self.user`` belongs to a group with ``name``."""
        user = self.user
        if not getattr(user, "is_authenticated", False):
            return False
        if self.group_names:
            return name in self.group_names

        def _exists() -> bool:
            return user.groups.filter(name=name).exists()

        return await sync_to_async(_exists)()

    async def login(
        self,
        username: str,
        password: str,
        *,
        login_fields: tuple[str, ...] | None = None,
    ) -> bool:
        """Authenticate with Django backends and establish a session.

        Returns:
            ``True`` on success, ``False`` on failure (also calls
            :meth:`on_auth_failed`).
        """
        request = current_request()
        if request is None:
            await self.on_auth_failed()
            return False
        fields = login_fields if login_fields is not None else DEFAULT_LOGIN_FIELDS
        user = await aauthenticate_login_fields(
            request,
            username.strip(),
            password,
            fields,
        )
        if user is None:
            await self.on_auth_failed()
            return False
        await alogin(request, user)
        await session_async_save(request)
        await self.refresh_django_user_fields()
        return True

    async def logout(self) -> None:
        """Clear the Django session for the current event."""
        request = current_request()
        if request is not None:
            await alogout(request)
            await session_async_save(request)
        await self.refresh_django_user_fields()

    async def on_auth_failed(self) -> Any:
        """Hook when :meth:`login` fails; override in subclasses."""
        return None

    async def on_permission_denied(self) -> Any:
        """Hook when permission checks fail; override in subclasses."""
        return rx.toast.error("You do not have permission to perform this action.")


def _iter_django_user_state_classes() -> Any:
    """Yield every registered :class:`~reflex_django.auth_state.DjangoUserState` subclass."""
    from reflex_django.auth_state import DjangoUserState

    seen: set[type] = set()
    stack: list[type] = [rx.State]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        if issubclass(cls, DjangoUserState):
            yield cls
        for sub in cls.get_substates():
            stack.append(sub)
    try:
        from reflex_django.auth.state_builders import get_or_create_django_auth_state

        auth_cls = get_or_create_django_auth_state()
        if auth_cls not in seen:
            yield auth_cls
    except ImportError:
        pass


def _resolve_substate_node(root: Any, state_cls: type) -> Any | None:
    """Return the live substate instance for ``state_cls``, or ``None``."""
    path = state_cls.get_full_name().split(".")
    try:
        return root.get_substate(path)
    except ValueError:
        return None


async def _sync_auth_snapshots_in_tree(
    state: Any,
    *,
    include_groups: bool | None = None,
) -> None:
    """Refresh auth snapshot vars on every :class:`~reflex_django.auth_state.DjangoUserState` substate."""
    from reflex_django.auth_state import (
        DjangoUserState,
        _auth_snapshot_owner,
        apply_auth_snapshot_to_state,
    )

    root = state._get_root_state() if hasattr(state, "_get_root_state") else state

    owners_seen: set[int] = set()
    nodes_seen: set[int] = set()

    async def sync_node(node: Any) -> None:
        try:
            from reflex_django.auth.state import DjangoAuthState
        except ImportError:
            DjangoAuthState = None  # type: ignore[misc, assignment]
        if not isinstance(node, DjangoUserState) and not (
            DjangoAuthState is not None and isinstance(node, DjangoAuthState)
        ):
            return
        nid = id(node)
        if nid in nodes_seen:
            return
        nodes_seen.add(nid)
        owner = _auth_snapshot_owner(node)
        oid = id(owner)
        if oid in owners_seen:
            return
        owners_seen.add(oid)
        await apply_auth_snapshot_to_state(owner, include_groups=include_groups)

    for state_cls in _iter_django_user_state_classes():
        node = _resolve_substate_node(root, state_cls)
        if node is not None:
            await sync_node(node)

    async def visit_instance_tree(node: Any) -> None:
        await sync_node(node)
        for child in (getattr(node, "substates", None) or {}).values():
            await visit_instance_tree(child)

    await visit_instance_tree(root)


async def maybe_sync_app_state_auth(state: Any) -> None:
    """Refresh auth snapshot vars on all ``DjangoUserState`` substates when auto-sync is enabled."""
    from django.conf import settings

    if not getattr(settings, "REFLEX_DJANGO_AUTH_AUTO_SYNC", True):
        return
    await _sync_auth_snapshots_in_tree(state)


__all__ = [
    "AuthBridgeMixin",
    "SessionProxy",
    "_sync_auth_snapshots_in_tree",
    "maybe_sync_app_state_auth",
    "session_async_save",
]
