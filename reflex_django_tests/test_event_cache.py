"""Tests for event bridge auth cache."""

from __future__ import annotations

import pytest
from django.conf import settings

from reflex_django.setup.conf import configure_django

configure_django()


@pytest.fixture(autouse=True)
def _use_locmem_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "CACHES",
        {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
        raising=False,
    )
    monkeypatch.setattr(settings, "RX_EVENT_CACHE", "default", raising=False)
    monkeypatch.setattr(settings, "RX_EVENT_CACHE_TTL", 60, raising=False)


def test_event_cache_round_trip() -> None:
    from reflex_django.bridge.cache import (
        get_cached_event_context,
        invalidate_event_cache,
        set_cached_event_context,
    )

    class _User:
        pk = 7
        is_authenticated = True

    class _Request:
        user = _User()

    set_cached_event_context("session-1", _Request())
    cached = get_cached_event_context("session-1")
    assert cached is not None
    assert cached.user_id == 7
    assert cached.is_authenticated is True

    invalidate_event_cache("session-1")
    assert get_cached_event_context("session-1") is None


def test_event_cache_disabled_when_ttl_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    from reflex_django.bridge.cache import (
        get_cached_event_context,
        set_cached_event_context,
    )

    monkeypatch.setattr(settings, "RX_EVENT_CACHE_TTL", 0, raising=False)

    class _User:
        pk = 1
        is_authenticated = True

    class _Request:
        user = _User()

    set_cached_event_context("session-2", _Request())
    assert get_cached_event_context("session-2") is None
