"""Re-export :mod:`reflex_django.auth_state` (v2 alias).

``DjangoUserState`` is defined in :mod:`reflex_django.auth_state` so compiled
frontend event handler keys stay stable across v1→v2 upgrades.
"""

from reflex_django.auth_state import (
    DjangoUserState,
    apply_auth_snapshot_for_event_handler,
    apply_auth_snapshot_to_state,
    user_snapshot,
)
from reflex_django.auth_state import (
    _auth_snapshot_owner,
    _mark_auth_snapshot_dirty_subtree,
    _mark_auth_ui_dirty,
    _mark_inherited_auth_snapshot_dirty,
)

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
