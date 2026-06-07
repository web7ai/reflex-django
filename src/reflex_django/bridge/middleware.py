"""Re-export DjangoEventBridge during bridge package migration."""

from reflex_django.middleware import DjangoEventBridge

__all__ = ["DjangoEventBridge"]