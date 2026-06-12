"""Tests for RXDJANGO_PROXY_SERVER resolution."""

from __future__ import annotations

import pytest

from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.setup.errors import ConfigurationError


def test_resolve_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RXDJANGO_PROXY_SERVER", "http://127.0.0.1:9000/")
    assert resolve_rxdjango_proxy_server() == "http://127.0.0.1:9000"


def test_resolve_from_deprecated_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RXDJANGO_PROXY_SERVER", raising=False)
    monkeypatch.setenv("REFLEX_DJANGO_HTTP_UPSTREAM", "http://127.0.0.1:8001")
    with pytest.warns(DeprecationWarning):
        assert resolve_rxdjango_proxy_server() == "http://127.0.0.1:8001"


def test_required_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RXDJANGO_PROXY_SERVER", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_HTTP_UPSTREAM", raising=False)
    with pytest.raises(ConfigurationError, match="RXDJANGO_PROXY_SERVER"):
        resolve_rxdjango_proxy_server(required=True)