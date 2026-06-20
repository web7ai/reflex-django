"""Opt-in timing hooks for the event bridge."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("reflex_django.bridge.metrics")


def _metrics_enabled() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "RX_EVENT_METRICS", False))
    except Exception:
        return False


def _metrics_logger() -> logging.Logger:
    try:
        from django.conf import settings

        name = getattr(settings, "RX_EVENT_METRICS_LOGGER", None)
        if isinstance(name, str) and name.strip():
            return logging.getLogger(name.strip())
    except Exception:
        pass
    return logger


@contextmanager
def measure_event_phase(phase: str) -> Iterator[None]:
    """Log elapsed milliseconds for *phase* when metrics are enabled."""
    if not _metrics_enabled():
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _metrics_logger().debug(
            "reflex-django event bridge phase=%s elapsed_ms=%.2f",
            phase,
            elapsed_ms,
        )


__all__ = ["measure_event_phase"]
