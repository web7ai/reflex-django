"""URL routing mode for the Reflex/Django ASGI dispatcher."""

from __future__ import annotations

import enum
import os


class UrlRoutingMode(enum.Enum):
    """How HTTP paths are split between Django and Reflex."""

    REFLEX_LED = "reflex_led"
    DJANGO_LED = "django_led"


def resolve_url_routing() -> UrlRoutingMode:
    """Resolve URL routing mode.

    Resolution order:

    1. ``REFLEX_DJANGO_URL_ROUTING`` env (``reflex_led`` | ``django_led``).
    2. ``settings.REFLEX_DJANGO_URL_ROUTING`` when Django is configured.
    3. Default: ``django_led``.
    """
    raw = os.environ.get("REFLEX_DJANGO_URL_ROUTING", "").strip().lower()
    if not raw:
        try:
            from django.conf import settings

            if settings.configured:
                raw = str(getattr(settings, "REFLEX_DJANGO_URL_ROUTING", "django_led")).lower()
        except Exception:
            raw = "django_led"
    if raw == "reflex_led":
        return UrlRoutingMode.REFLEX_LED
    return UrlRoutingMode.DJANGO_LED
