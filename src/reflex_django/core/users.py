"""Small helpers for working with Django user objects in Reflex handlers."""

from __future__ import annotations

from typing import Any


def username_str(user: Any) -> str:
    """Return a display username from a Django or anonymous user."""
    getusername = getattr(user, "get_username", None)
    if callable(getusername):
        return str(getusername())
    return str(getattr(user, "username", "") or "")


__all__ = ["username_str"]
