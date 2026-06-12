"""Registry for :func:`reflex_django.django.urls.reflex_mount` patterns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReflexMountRegistration:
    """A registered Reflex SPA mount in Django URLconf."""

    prefix: str
    pattern: str


MOUNT_REGISTRY: list[ReflexMountRegistration] = []


def register_mount(prefix: str, pattern: str) -> None:
    """Record a mount for introspection and tests."""
    MOUNT_REGISTRY.append(ReflexMountRegistration(prefix=prefix, pattern=pattern))


def clear_mount_registry() -> None:
    """Clear registrations (tests only)."""
    MOUNT_REGISTRY.clear()
