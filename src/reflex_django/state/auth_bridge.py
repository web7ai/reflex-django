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
        """Bridged Django request + context processors for the current event."""
        from reflex_django.context import current_request, get_request_reflex_context
        from reflex_django.state.request import DjangoStateRequest
        from reflex_django.state.request_binding import REQUEST_WRAPPER_ATTR

        try:
            cached = object.__getattribute__(self, REQUEST_WRAPPER_ATTR)
        except AttributeError:
            cached = None
        if cached is not None:
            return cached

        http = current_request()
        if http is None:
            msg = (
                "No Django request is bound to this Reflex event. "
                "Use self.request only inside @rx.event handlers (e.g. on_load), "
                "not in class-level defaults or UI rendering."
            )
            raise RuntimeError(msg)
        return DjangoStateRequest(http, get_request_reflex_context(http))

    @property
    def django_context(self) -> dict[str, Any]:
        """Merged context-processor dict for the current event (read-only copy)."""
        from reflex_django.context import current_request, get_request_reflex_context

        return get_request_reflex_context(current_request())

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

    async def refresh_django_user_fields(
        self,
        *,
        include_groups: bool | None = None,
    ) -> None:
        """Update auth snapshot vars on this substate from :func:`current_user`."""
        from reflex_django.auth_state import apply_auth_snapshot_to_state

        await apply_auth_snapshot_to_state(self, include_groups=include_groups)

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
        sk = getattr(request.session, "session_key", None) or ""
        if sk:
            from reflex_django.session_js import mirror_auth_cookies_to_state_tree

            mirror_auth_cookies_to_state_tree(self, sk)
        await self.refresh_django_user_fields()
        return True

    async def logout(self) -> None:
        """Log out, flush the Django session, and drop stale cookie mirrors.

        ``alogout`` calls :meth:`~django.contrib.sessions.backends.base.SessionBase.flush`,
        which deletes session data and rotates the session key. This method also
        removes session/CSRF cookies from the synthetic request and from persisted
        ``router_data`` on the Reflex state tree so later events in the same page
        life do not resurrect the old session. Pair with
        :func:`~reflex_django.session_js.browser_auth_logout_clear_js` (via
        :func:`~reflex_django.mixins.session_auth._sync_session_cookie_then_nav`)
        when the browser must drop cookies and Reflex client storage before the
        next document load.
        """
        from reflex_django.session_js import (
            clear_auth_cookies_from_state_tree,
            strip_auth_cookies_from_request,
        )

        request = current_request()
        if request is not None:
            await alogout(request)
            strip_auth_cookies_from_request(request)
            await session_async_save(request)
        clear_auth_cookies_from_state_tree(self)
        await self.refresh_django_user_fields()

    async def on_auth_failed(self) -> Any:
        """Hook when :meth:`login` fails; override in subclasses."""
        return None

    async def on_permission_denied(self) -> Any:
        """Hook when permission checks fail; override in subclasses."""
        return rx.toast.error("You do not have permission to perform this action.")

    async def load_django_context(self) -> dict[str, Any]:
        """Re-run context processors and refresh the cached request context.

        Not required on each event when ``REFLEX_DJANGO_AUTO_LOAD_CONTEXT`` is
        ``True`` (default): :class:`~reflex_django.middleware.DjangoEventBridge`
        already loads context before your handler runs. Call this only when you
        need a forced refresh mid-handler.

        Returns:
            Merged JSON-safe context dict (same keys as ``self.request`` attrs
            from processors, e.g. template ``auth`` context when enabled).
        """
        from reflex_django.context import (
            current_request,
            get_request_reflex_context,
            set_request_reflex_context,
        )
        from reflex_django.reflex_context import collect_reflex_context

        http = current_request()
        if http is None:
            return {}
        merged = await collect_reflex_context(http)
        set_request_reflex_context(http, merged)
        return merged


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


async def maybe_sync_django_context_state(state: Any) -> None:
    """Copy bridged context onto :class:`~reflex_django.reflex_context.DjangoContextState` substates."""
    import json

    from django.conf import settings

    if not getattr(settings, "REFLEX_DJANGO_AUTO_LOAD_CONTEXT", True):
        return

    from reflex_django.context import current_request, get_request_reflex_context
    from reflex_django.reflex_context import DjangoContextState

    merged = get_request_reflex_context(current_request())
    payload = json.dumps(merged, indent=2, sort_keys=True, default=str)

    root = state._get_root_state() if hasattr(state, "_get_root_state") else state

    def visit(node: Any) -> None:
        if isinstance(node, DjangoContextState):
            node.django_context = merged
            node.django_context_json = payload
        for child in (getattr(node, "substates", None) or {}).values():
            visit(child)

    visit(root)


__all__ = [
    "AuthBridgeMixin",
    "SessionProxy",
    "_sync_auth_snapshots_in_tree",
    "maybe_sync_app_state_auth",
    "maybe_sync_django_context_state",
    "session_async_save",
]
