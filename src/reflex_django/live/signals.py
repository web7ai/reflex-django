"""Connect Django model signals to the live broadcaster.

``register_live_model(Model)`` wires ``post_save``/``post_delete`` so every write
publishes a :class:`ModelChange`. Registration is idempotent per model.
"""

from __future__ import annotations

import threading
from typing import Any

from django.db.models.signals import post_delete, post_save

from reflex_django.live.broadcaster import live_broadcaster
from reflex_django.live.change import (
    ACTION_CREATED,
    ACTION_DELETED,
    ACTION_UPDATED,
    ModelChange,
)

_REGISTERED: set[str] = set()
_LOCK = threading.Lock()


def model_label(model: Any) -> str:
    meta = model._meta
    return f"{meta.app_label}.{meta.model_name}"


def _on_save(sender: Any, instance: Any, created: bool, **_: Any) -> None:
    live_broadcaster().publish(
        ModelChange(
            model_label=model_label(sender),
            action=ACTION_CREATED if created else ACTION_UPDATED,
            pk=instance.pk,
        )
    )


def _on_delete(sender: Any, instance: Any, **_: Any) -> None:
    live_broadcaster().publish(
        ModelChange(
            model_label=model_label(sender),
            action=ACTION_DELETED,
            pk=instance.pk,
        )
    )


def register_live_model(model: Any) -> None:
    """Idempotently connect change signals for *model*."""
    label = model_label(model)
    with _LOCK:
        if label in _REGISTERED:
            return
        _REGISTERED.add(label)
    post_save.connect(
        _on_save, sender=model, dispatch_uid=f"rxd_live_save_{label}", weak=False
    )
    post_delete.connect(
        _on_delete, sender=model, dispatch_uid=f"rxd_live_delete_{label}", weak=False
    )


def unregister_live_model(model: Any) -> None:
    """Disconnect change signals for *model* (used in tests/teardown)."""
    label = model_label(model)
    with _LOCK:
        _REGISTERED.discard(label)
    post_save.disconnect(sender=model, dispatch_uid=f"rxd_live_save_{label}")
    post_delete.disconnect(sender=model, dispatch_uid=f"rxd_live_delete_{label}")


def is_live_model(model: Any) -> bool:
    return model_label(model) in _REGISTERED


__all__ = [
    "is_live_model",
    "model_label",
    "register_live_model",
    "unregister_live_model",
]
