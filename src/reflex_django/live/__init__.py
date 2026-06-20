"""Reactive live updates for ``ModelState`` via Django model signals.

Public surface:

* :func:`register_live_model` / :func:`unregister_live_model` - connect signals.
* :class:`ModelChange` - the broadcast payload.
* :func:`live_broadcaster` - the process-wide fan-out singleton.
* :class:`LiveListMixin` - mix into a ``ModelState`` for live list patching.
"""

from __future__ import annotations

from reflex_django.live.broadcaster import LiveBroadcaster, live_broadcaster
from reflex_django.live.change import (
    ACTION_CREATED,
    ACTION_DELETED,
    ACTION_UPDATED,
    ModelChange,
)
from reflex_django.live.signals import (
    is_live_model,
    model_label,
    register_live_model,
    unregister_live_model,
)


def __getattr__(name: str):
    # Lazy import so the signal/broadcast helpers can be used without importing
    # Reflex unless the state mixin is needed.
    if name == "LiveListMixin":
        from reflex_django.live.state import LiveListMixin

        return LiveListMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ACTION_CREATED",
    "ACTION_DELETED",
    "ACTION_UPDATED",
    "LiveBroadcaster",
    "LiveListMixin",
    "ModelChange",
    "is_live_model",
    "live_broadcaster",
    "model_label",
    "register_live_model",
    "unregister_live_model",
]
