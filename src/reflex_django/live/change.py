"""The change event broadcast when a live-tracked model row is written."""

from __future__ import annotations

from dataclasses import dataclass

ACTION_CREATED = "created"
ACTION_UPDATED = "updated"
ACTION_DELETED = "deleted"


@dataclass(frozen=True)
class ModelChange:
    """A single create/update/delete on a tracked model."""

    model_label: str
    action: str
    pk: int | str | None

    @property
    def is_delete(self) -> bool:
        return self.action == ACTION_DELETED

    @property
    def is_create(self) -> bool:
        return self.action == ACTION_CREATED


__all__ = [
    "ACTION_CREATED",
    "ACTION_DELETED",
    "ACTION_UPDATED",
    "ModelChange",
]
