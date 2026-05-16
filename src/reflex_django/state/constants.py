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

# Default reactive var names for :class:`~reflex_django.state.ModelState`.
DEFAULT_LIST_VAR = "data"
DEFAULT_ERROR_VAR = "error"
DEFAULT_FIELD_ERRORS_VAR = "field_errors"
DEFAULT_SEARCH_VAR = "search"
DEFAULT_ORDERING_VAR = "ordering"
DEFAULT_TOTAL_COUNT_VAR = "total_count"
DEFAULT_PAGE_COUNT_VAR = "page_count"

__all__ = [
    "ACTION_CANCEL_EDIT",
    "ACTION_DELETE",
    "ACTION_LOAD_LIST",
    "ACTION_SAVE",
    "ACTION_START_EDIT",
    "DEFAULT_ERROR_VAR",
    "DEFAULT_FIELD_ERRORS_VAR",
    "DEFAULT_LIST_VAR",
    "DEFAULT_LOGIN_REQUIRED_ACTIONS",
    "DEFAULT_ORDERING_VAR",
    "DEFAULT_PAGE_COUNT_VAR",
    "DEFAULT_SEARCH_VAR",
    "DEFAULT_TOTAL_COUNT_VAR",
]
