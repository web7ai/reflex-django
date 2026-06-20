"""Tests for RX_PROXY_SERVER resolution."""

from __future__ import annotations

import pytest

from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.setup.errors import ConfigurationError


def test_resolve_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RX_PROXY_SERVER", "http://127.0.0.1:9000/")
    assert resolve_rxdjango_proxy_server() == "http://127.0.0.1:9000"


def test_resolve_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from django.conf import settings

    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    monkeypatch.setattr(
        settings, "RX_PROXY_SERVER", "http://127.0.0.1:8001", raising=False
    )
    assert resolve_rxdjango_proxy_server() == "http://127.0.0.1:8001"


def test_required_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigurationError, match="RX_PROXY_SERVER"):
        resolve_rxdjango_proxy_server(required=True)
