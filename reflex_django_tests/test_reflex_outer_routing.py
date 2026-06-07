"""Tests for reflex_outer routing mode."""

from __future__ import annotations

import pytest

from reflex_django.routing import UrlRoutingMode, resolve_url_routing


def test_resolve_reflex_outer_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_URL_ROUTING", "reflex_outer")
    assert resolve_url_routing() == UrlRoutingMode.REFLEX_OUTER


def test_build_application_uses_reflex_outer_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_URL_ROUTING", "reflex_outer")
    import reflex_django.asgi_entry as entry

    entry._application = None
    called = {"reflex": False}

    def _fake_reflex_outer() -> object:
        called["reflex"] = True

        async def app(scope, receive, send):
            return None

        return app

    monkeypatch.setattr(entry, "_build_reflex_outer_application", _fake_reflex_outer)
    monkeypatch.setattr(
        entry,
        "build_django_outer_application",
        lambda: (_ for _ in ()).throw(AssertionError("should not use django outer")),
    )
    app = entry.build_application()
    assert called["reflex"] is True
    assert callable(app)
