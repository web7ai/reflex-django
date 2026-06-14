"""Integration mode detection: Reflex-first plugin vs Django-first settings."""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

logger = logging.getLogger("reflex_django.runtime.integration.modes")

_ACTIVE_MODE: IntegrationMode | None = None


class IntegrationMode(Enum):
    """How reflex-django bootstraps relative to Reflex and Django."""

    REFLEX_FIRST = "reflex_first"
    DJANGO_FIRST = "django_first"
    NONE = "none"


def get_active_integration_mode() -> IntegrationMode:
    """Return the active integration mode for the current process."""
    if _ACTIVE_MODE is not None:
        return _ACTIVE_MODE
    return IntegrationMode.NONE


def set_active_integration_mode(mode: IntegrationMode) -> None:
    """Record the active integration mode (tests may reset via ``clear_active_mode``)."""
    global _ACTIVE_MODE
    _ACTIVE_MODE = mode


def clear_active_integration_mode() -> None:
    """Reset mode tracking (tests only)."""
    global _ACTIVE_MODE
    _ACTIVE_MODE = None


def detect_reflex_django_plugin(config: Any) -> Any | None:
    """Return the :class:`~reflex_django.plugins.ReflexDjangoPlugin` from *config*, if any."""
    from reflex_django.plugins.reflex_django import is_reflex_django_plugin

    for plugin in getattr(config, "plugins", None) or ():
        if is_reflex_django_plugin(plugin):
            return plugin
    return None


def _load_rxconfig_for_detection() -> Any | None:
    """Best-effort load of on-disk ``rxconfig`` without django-first synthesis."""
    try:
        from reflex_django.runtime.integration.registry import get_original_get_config

        original = get_original_get_config()
        if original is not None:
            return original(reload=False)
    except Exception:
        pass
    try:
        from reflex_base.config import get_config

        return get_config(reload=False)
    except Exception:
        return None


def _django_first_available() -> bool:
    """Return whether a Django-first bootstrap is appropriate."""
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        return True
    from reflex_django.setup.project import discover_settings_module

    return discover_settings_module() is not None


def resolve_integration_mode(*, config: Any | None = None) -> IntegrationMode:
    """Resolve how reflex-django should integrate for the current process."""
    if config is None:
        config = _load_rxconfig_for_detection()

    if config is not None:
        if detect_reflex_django_plugin(config) is not None:
            return IntegrationMode.REFLEX_FIRST

    if _django_first_available():
        return IntegrationMode.DJANGO_FIRST

    return IntegrationMode.NONE
