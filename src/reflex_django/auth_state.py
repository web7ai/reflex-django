"""Reflex :class:`reflex.state.State` helpers for mirroring Django auth in UI state.

Server handlers should still use :func:`reflex_django.current_user` for
authorization; the fields here are JSON snapshots for the frontend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx
from reflex_django.context import current_user
from reflex_django.state.auth_bridge import AuthBridgeMixin

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser


def _username_str(user: Any) -> str:
    getusername = getattr(user, "get_username", None)
    if callable(getusername):
        return str(getusername())
    return str(getattr(user, "username", "") or "")


def user_snapshot(
    user: AbstractBaseUser | AnonymousUser,
    *,
    group_names: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable dict from a Django user instance.

    Args:
        user: Django user or anonymous user.
        group_names: Optional list of group names (caller supplies when needed).

    Returns:
        Keys: ``id``, ``username``, ``email``, ``first_name``, ``last_name``,
        ``is_authenticated``, ``is_staff``, ``is_superuser``, ``group_names``.
    """
    auth = bool(getattr(user, "is_authenticated", False))
    groups = list(group_names) if group_names is not None else []
    if not auth:
        return {
            "id": None,
            "username": "",
            "email": "",
            "first_name": "",
            "last_name": "",
            "is_authenticated": False,
            "is_staff": False,
            "is_superuser": False,
            "group_names": [],
        }
    uid = getattr(user, "pk", None)
    return {
        "id": int(uid) if uid is not None else None,
        "username": _username_str(user),
        "email": str(getattr(user, "email", "") or ""),
        "first_name": str(getattr(user, "first_name", "") or ""),
        "last_name": str(getattr(user, "last_name", "") or ""),
        "is_authenticated": True,
        "is_staff": bool(getattr(user, "is_staff", False)),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "group_names": groups,
    }


def _settings_include_groups() -> bool:
    from django.conf import settings

    return bool(getattr(settings, "REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS", False))


async def _group_names_for_user(user: Any) -> list[str]:
    from django.contrib.auth.models import AnonymousUser

    if isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return []
    return [name async for name in user.groups.values_list("name", flat=True)]


_AUTH_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "user_id",
    "username",
    "email",
    "first_name",
    "last_name",
    "is_authenticated",
    "is_staff",
    "is_superuser",
    "group_names",
    "messages",
    "csrf_token",
    "language",
    "language_bidi",
)


def _auth_snapshot_owner(state: Any) -> Any:
    """Return the substate that owns auth snapshot vars (not inherited)."""
    node = state
    while node is not None and "is_authenticated" in getattr(node, "inherited_vars", {}):
        node = node.parent_state
    return node if node is not None else state


def _mark_inherited_auth_snapshot_dirty(state: Any) -> None:
    """Mark inherited auth fields dirty on *state* and all descendant substates."""
    _mark_auth_snapshot_dirty_subtree(state)


def _mark_auth_snapshot_dirty_subtree(root_node: Any) -> None:
    """Mark inherited auth fields dirty on *root_node* and its descendants only.

    Used for page handler branches so we do not walk unrelated substates (which
    can emit deltas for dispatch keys the browser never compiled).
    """
    def visit(node: Any) -> None:
        for field in _AUTH_SNAPSHOT_FIELDS:
            if field in getattr(node, "inherited_vars", {}):
                node.dirty_vars.add(field)
        mark_dirty = getattr(node, "_mark_dirty", None)
        if callable(mark_dirty):
            mark_dirty()
        substates = getattr(node, "substates", None) or {}
        if isinstance(substates, dict):
            for child in substates.values():
                visit(child)

    visit(root_node)


def _mark_auth_ui_dirty(state: Any) -> None:
    """Force UI re-render for inherited ``is_authenticated`` on a substate."""
    if "is_authenticated" in getattr(state, "inherited_vars", {}):
        state.dirty_vars.add("is_authenticated")
        mark_dirty = getattr(state, "_mark_dirty", None)
        if callable(mark_dirty):
            mark_dirty()


def _sync_django_auth_substates(root: Any) -> None:
    """Walk the instance tree and mark auth UI dirty on every ``DjangoAuthState``."""
    try:
        from reflex_django.auth.state import DjangoAuthState
    except ImportError:
        return

    def visit(node: Any) -> None:
        if isinstance(node, DjangoAuthState):
            _mark_auth_ui_dirty(node)
        for child in (getattr(node, "substates", None) or {}).values():
            visit(child)

    visit(root)


def _can_assign_auth_field_on_owner(owner: Any, field: str) -> bool:
    """Return whether *field* can be assigned on *owner* (not inherited without parent)."""
    if field not in getattr(owner, "inherited_vars", {}):
        return True
    return getattr(owner, "parent_state", None) is not None


def _owner_matches_auth_snapshot(owner: Any, snap: dict[str, Any]) -> bool:
    """Return whether *owner* already reflects *snap* (skip redundant deltas)."""
    try:
        from reflex_django.auth.state import DjangoAuthState
    except ImportError:
        DjangoAuthState = None  # type: ignore[misc, assignment]
    skip_auth_flag = DjangoAuthState is not None and isinstance(owner, DjangoAuthState)
    checks: list[tuple[str, Any]] = [
        ("user_id", snap["id"]),
        ("username", snap["username"]),
        ("email", snap["email"]),
        ("first_name", snap["first_name"]),
        ("last_name", snap["last_name"]),
        ("is_staff", snap["is_staff"]),
        ("is_superuser", snap["is_superuser"]),
        ("group_names", snap["group_names"]),
    ]
    if not skip_auth_flag:
        checks.append(("is_authenticated", snap["is_authenticated"]))

    # Mirror fields are populated per-event from the bridged middleware chain;
    # include them in the match check so a new flash message (or a fresh CSRF
    # token, or a language switch) reliably triggers a UI delta.
    mirror = _collect_middleware_mirror_snapshot()
    for field, expected in (
        ("messages", mirror["messages"]),
        ("csrf_token", mirror["csrf_token"]),
        ("language", mirror["language"]),
        ("language_bidi", mirror["language_bidi"]),
    ):
        if _can_assign_auth_field_on_owner(owner, field):
            checks.append((field, expected))

    for field, expected in checks:
        if not _can_assign_auth_field_on_owner(owner, field):
            continue
        if getattr(owner, field, None) != expected:
            return False
    return True


def _collect_middleware_mirror_snapshot() -> dict[str, Any]:
    """Snapshot middleware-side data (messages, CSRF, language) for the UI.

    Each item is opt-out via a per-setting flag so users can disable mirroring
    individually (saves event payload size on apps that do not need it).
    """
    from django.conf import settings

    snap: dict[str, Any] = {
        "messages": [],
        "csrf_token": "",
        "language": "",
        "language_bidi": False,
    }

    if getattr(settings, "REFLEX_DJANGO_MIRROR_MESSAGES", True):
        try:
            from reflex_django.context import current_messages

            snap["messages"] = current_messages()
        except Exception:
            snap["messages"] = []

    if getattr(settings, "REFLEX_DJANGO_MIRROR_CSRF", True):
        try:
            from reflex_django.context import current_csrf_token

            snap["csrf_token"] = current_csrf_token()
        except Exception:
            snap["csrf_token"] = ""

    if getattr(settings, "REFLEX_DJANGO_MIRROR_LANGUAGE", True):
        try:
            from django.utils import translation

            snap["language"] = str(translation.get_language() or "")
            snap["language_bidi"] = bool(translation.get_language_bidi())
        except Exception:
            snap["language"] = ""
            snap["language_bidi"] = False
    return snap


async def _write_auth_snapshot_to_owner(
    owner: Any,
    snap: dict[str, Any],
) -> None:
    """Assign snapshot fields onto the substate that owns auth vars."""
    try:
        from reflex_django.auth.state import DjangoAuthState
    except ImportError:
        DjangoAuthState = None  # type: ignore[misc, assignment]
    skip_auth_flag = DjangoAuthState is not None and isinstance(owner, DjangoAuthState)
    if _can_assign_auth_field_on_owner(owner, "user_id"):
        owner.user_id = snap["id"]
    if _can_assign_auth_field_on_owner(owner, "username"):
        owner.username = snap["username"]
    if _can_assign_auth_field_on_owner(owner, "email"):
        owner.email = snap["email"]
    if _can_assign_auth_field_on_owner(owner, "first_name"):
        owner.first_name = snap["first_name"]
    if _can_assign_auth_field_on_owner(owner, "last_name"):
        owner.last_name = snap["last_name"]
    if not skip_auth_flag and _can_assign_auth_field_on_owner(owner, "is_authenticated"):
        owner.is_authenticated = snap["is_authenticated"]
    if _can_assign_auth_field_on_owner(owner, "is_staff"):
        owner.is_staff = snap["is_staff"]
    if _can_assign_auth_field_on_owner(owner, "is_superuser"):
        owner.is_superuser = snap["is_superuser"]
    if _can_assign_auth_field_on_owner(owner, "group_names"):
        owner.group_names = snap["group_names"]

    mirror = _collect_middleware_mirror_snapshot()
    if _can_assign_auth_field_on_owner(owner, "messages"):
        owner.messages = mirror["messages"]
    if _can_assign_auth_field_on_owner(owner, "csrf_token"):
        owner.csrf_token = mirror["csrf_token"]
    if _can_assign_auth_field_on_owner(owner, "language"):
        owner.language = mirror["language"]
    if _can_assign_auth_field_on_owner(owner, "language_bidi"):
        owner.language_bidi = mirror["language_bidi"]


async def apply_auth_snapshot_for_event_handler(
    handler: Any,
    *,
    include_groups: bool | None = None,
) -> None:
    """Update auth snapshots for a page handler without walking the full state tree.

    Used from :func:`~reflex_django.state.auth_bridge.maybe_sync_app_state_auth`
    when ``HomeState(AppState).on_load`` runs. Writes on the handler's field owner
    (usually a parent ``DjangoUserState`` substate) and only marks the handler branch
    dirty when values change, so anonymous guests do not emit redundant parent
    substates deltas that can trigger ``dispatch is not a function``.
    """
    if not isinstance(handler, DjangoUserState):
        return

    owner = _auth_snapshot_owner(handler)
    if not isinstance(owner, DjangoUserState):
        return
    user = current_user()
    want_groups = (
        _settings_include_groups() if include_groups is None else include_groups
    )
    groups = await _group_names_for_user(user) if want_groups else None
    snap = user_snapshot(user, group_names=groups if want_groups else [])
    if _owner_matches_auth_snapshot(owner, snap):
        return
    await _write_auth_snapshot_to_owner(owner, snap)
    _mark_auth_snapshot_dirty_subtree(handler)


async def apply_auth_snapshot_to_state(
    state: DjangoUserState,
    *,
    include_groups: bool | None = None,
) -> None:
    """Update auth snapshot vars on ``state`` from :func:`current_user`.

    Plain async helper for server-side code (event bridge, mixins). Reflex may
    wrap :meth:`DjangoUserState.refresh_django_user_fields` as an event handler;
    call this function when you need a direct coroutine.

    Writes to the substate that **owns** the fields (usually ``DjangoUserState``),
    then marks inherited auth fields dirty on descendant substates so bindings on
    ``DjangoAuthState`` and ``AppState`` branches re-render.
    """
    owner = _auth_snapshot_owner(state)
    user = current_user()
    want_groups = (
        _settings_include_groups() if include_groups is None else include_groups
    )
    groups = await _group_names_for_user(user) if want_groups else None
    snap = user_snapshot(user, group_names=groups if want_groups else [])
    await _write_auth_snapshot_to_owner(owner, snap)
    _mark_inherited_auth_snapshot_dirty(owner)
    root = owner._get_root_state() if hasattr(owner, "_get_root_state") else owner
    _sync_django_auth_substates(root)


class DjangoUserState(AuthBridgeMixin, rx.State):
    """Snapshot of ``request.user`` and middleware state for the Reflex UI.

    Auth fields (``username``, ``is_authenticated``, …) and middleware mirrors
    (``messages``, ``csrf_token``, ``language``) are populated automatically
    by the event bridge after the full ``settings.MIDDLEWARE`` chain runs.
    Use these in your UI (e.g. ``rx.cond(State.is_authenticated, ...)``,
    ``rx.foreach(State.messages, render_message)``).

    Call :meth:`sync_from_django` from ``on_load`` to force a refresh.
    """

    user_id: int | None = None
    username: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    is_authenticated: bool = False
    is_staff: bool = False
    is_superuser: bool = False
    group_names: list[str] = []
    messages: list[dict[str, Any]] = []
    csrf_token: str = ""
    language: str = ""
    language_bidi: bool = False

    @rx.event
    async def sync_from_django(
        self,
        *,
        include_groups: bool | None = None,
    ) -> None:
        """Refresh snapshot fields from :func:`reflex_django.current_user`.

        Updates every :class:`DjangoUserState` substate in the client tree
        (including :class:`~reflex_django.auth.state.DjangoAuthState`) so UI
        bindings like ``DjangoAuthState.is_authenticated`` stay aligned when
        ``on_load`` targets :class:`DjangoUserState`.

        Args:
            include_groups: When ``None``, use
                ``settings.REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS``.
                When ``True``, load group names with one async query.
        """
        from reflex_django.state.auth_bridge import _sync_auth_snapshots_in_tree

        await _sync_auth_snapshots_in_tree(self, include_groups=include_groups)


__all__ = [
    "DjangoUserState",
    "_auth_snapshot_owner",
    "_mark_auth_snapshot_dirty_subtree",
    "_mark_auth_ui_dirty",
    "_mark_inherited_auth_snapshot_dirty",
    "apply_auth_snapshot_for_event_handler",
    "apply_auth_snapshot_to_state",
    "user_snapshot",
]
