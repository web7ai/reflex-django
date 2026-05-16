"""Action names for :class:`~reflex_django.state.mixins.dispatch.DispatchMixin`."""

from __future__ import annotations

ACTION_LOAD_LIST = "load_list"
ACTION_SAVE = "save"
ACTION_DELETE = "delete"
ACTION_START_EDIT = "start_edit"
ACTION_CANCEL_EDIT = "cancel_edit"

DEFAULT_LOGIN_REQUIRED_ACTIONS = frozenset(
    {
        ACTION_LOAD_LIST,
        ACTION_SAVE,
        ACTION_DELETE,
        ACTION_START_EDIT,
    }
)

__all__ = [
    "ACTION_CANCEL_EDIT",
    "ACTION_DELETE",
    "ACTION_LOAD_LIST",
    "ACTION_SAVE",
    "ACTION_START_EDIT",
    "DEFAULT_LOGIN_REQUIRED_ACTIONS",
]
