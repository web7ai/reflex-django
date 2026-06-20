"""Tests for the cached auth_only fast path (:mod:`reflex_django.bridge.auth_fast_path`)."""

from __future__ import annotations

import asyncio
from unittest import mock

from django.test import override_settings

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.bridge import auth_fast_path  # noqa: E402
from reflex_django.bridge.cache import CachedEventContext  # noqa: E402


def _request() -> object:
    from django.http import HttpRequest

    req = HttpRequest()
    req.COOKIES["sessionid"] = "abc123"
    return req


@override_settings(RX_EVENT_CACHE_FAST_AUTH=False)
def test_fast_path_disabled_by_default() -> None:
    async def run() -> bool:
        return await auth_fast_path.try_apply_cached_auth(_request(), "abc123")

    assert asyncio.run(run()) is False


@override_settings(RX_EVENT_CACHE_FAST_AUTH=True, RX_EVENT_CACHE_TTL=60)
def test_fast_path_no_cache_entry_falls_back() -> None:
    async def run() -> bool:
        with mock.patch(
            "reflex_django.bridge.cache.get_cached_event_context",
            return_value=None,
        ):
            return await auth_fast_path.try_apply_cached_auth(_request(), "abc123")

    assert asyncio.run(run()) is False


@override_settings(RX_EVENT_CACHE_FAST_AUTH=True, RX_EVENT_CACHE_TTL=60)
def test_fast_path_anonymous_cache_skips_middleware() -> None:
    req = _request()

    async def run() -> bool:
        with mock.patch(
            "reflex_django.bridge.cache.get_cached_event_context",
            return_value=CachedEventContext(user_id=None, is_authenticated=False),
        ):
            return await auth_fast_path.try_apply_cached_auth(req, "abc123")

    used = asyncio.run(run())
    assert used is True
    # Anonymous user seeded without a DB query; session attached lazily.
    assert getattr(req, "user").is_authenticated is False
    assert getattr(req, "session", None) is not None


@override_settings(RX_EVENT_CACHE_FAST_AUTH=True, RX_EVENT_CACHE_TTL=60)
def test_fast_path_authenticated_resolves_by_pk() -> None:
    req = _request()
    sentinel_user = mock.Mock()
    sentinel_user.is_authenticated = True

    async def run() -> bool:
        with (
            mock.patch(
                "reflex_django.bridge.cache.get_cached_event_context",
                return_value=CachedEventContext(user_id=7, is_authenticated=True),
            ),
            mock.patch(
                "reflex_django.bridge.auth_fast_path._aresolve_cached_user",
                new=mock.AsyncMock(return_value=sentinel_user),
            ),
        ):
            return await auth_fast_path.try_apply_cached_auth(req, "abc123")

    used = asyncio.run(run())
    assert used is True
    assert getattr(req, "user") is sentinel_user
