"""Re-export DjangoEventBridge during bridge package migration."""

from reflex_django.bridge.django_event import DjangoEventBridge

__all__ = ["DjangoEventBridge"]