"""Django signals for reflex-django extension hooks."""

from django.dispatch import Signal

event_bridge_cache_invalidated = Signal()

__all__ = ["event_bridge_cache_invalidated"]