"""Reflex :class:`reflex.state.State` helpers for mirroring Django auth in UI state.

Server handlers should still use :func:`reflex_django.current_user` for
authorization; the fields here are JSON snapshots for the frontend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx
from reflex_django.context import current_user

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


class DjangoUserState(rx.State):
    """Snapshot of ``request.user`` for Reflex UI (navbar, conditional layout).

    Call :meth:`sync_from_django` from ``on_load`` or after login/logout.
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

    async def refresh_django_user_fields(
        self,
        *,
        include_groups: bool | None = None,
    ) -> None:
        """Update snapshot vars from :func:`current_user` (callable from any coroutine).

        Args:
            include_groups: Same semantics as :meth:`sync_from_django`.
        """
        user = current_user()
        want_groups = (
            _settings_include_groups() if include_groups is None else include_groups
        )
        groups = await _group_names_for_user(user) if want_groups else None
        snap = user_snapshot(user, group_names=groups if want_groups else [])
        self.user_id = snap["id"]
        self.username = snap["username"]
        self.email = snap["email"]
        self.first_name = snap["first_name"]
        self.last_name = snap["last_name"]
        self.is_authenticated = snap["is_authenticated"]
        self.is_staff = snap["is_staff"]
        self.is_superuser = snap["is_superuser"]
        self.group_names = snap["group_names"]

    @rx.event
    async def sync_from_django(
        self,
        *,
        include_groups: bool | None = None,
    ) -> None:
        """Refresh snapshot fields from :func:`reflex_django.current_user`.

        Args:
            include_groups: When ``None``, use
                ``settings.REFLEX_DJANGO_USER_SNAPSHOT_INCLUDE_GROUPS``.
                When ``True``, load group names with one async query.
        """
        await self.refresh_django_user_fields(include_groups=include_groups)


__all__ = ["DjangoUserState", "user_snapshot"]
