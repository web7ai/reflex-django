"""Opt-in debug logging for reflex-django internals.

Several hot paths in the event bridge intentionally swallow exceptions so a
single bad event cannot crash the socket handler. That makes real bugs hard to
diagnose. :func:`debug_log_exception` logs the active exception (with
traceback) only when debug logging is explicitly enabled, so production stays
quiet while developers can opt in.

Enable via either:

- the environment variable ``RX_BRIDGE_DEBUG`` (``1``/``true``/``yes``/``on``), or
- the Django setting ``RX_BRIDGE_DEBUG = True``.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("reflex_django")

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def bridge_debug_enabled() -> bool:
    """Return whether verbose reflex-django bridge debug logging is enabled."""
    env = os.environ.get("RX_BRIDGE_DEBUG", "").strip().lower()
    if env in _TRUTHY:
        return True
    try:
        from django.conf import settings

        return bool(getattr(settings, "RX_BRIDGE_DEBUG", False))
    except Exception:
        return False


def debug_log_exception(message: str) -> None:
    """Log the active exception with traceback when bridge debug is enabled.

    A no-op when debug logging is off, so callers can wrap intentional
    ``except`` blocks without adding noise in production.

    Args:
        message: Short context describing what was being attempted.
    """
    if bridge_debug_enabled():
        logger.exception("reflex-django: %s", message)


__all__ = ["bridge_debug_enabled", "debug_log_exception"]
