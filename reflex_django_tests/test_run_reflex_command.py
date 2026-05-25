"""Tests for the run_reflex management command."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from reflex_django.management.commands.run_reflex import Command
from reflex_django.routing import UrlRoutingMode


def test_run_reflex_invokes_reflex_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy Reflex-led routing modes delegate to ``reflex run`` CLI verbatim.

    ``DJANGO_OUTER`` (the new default) takes a different code path entirely
    (it spawns Vite + uvicorn locally), so we pin the routing mode to a
    legacy value for this test.
    """
    captured_argv: list[str] = []

    def _capture_main(**_kwargs: object) -> None:
        captured_argv[:] = list(sys.argv)

    cli_mock = mock.MagicMock()
    cli_mock.commands = {"run": mock.MagicMock()}
    cli_mock.main = _capture_main

    import reflex.reflex as reflex_module

    monkeypatch.setattr(reflex_module, "cli", cli_mock)
    install_mock = mock.MagicMock(return_value=mock.Mock())
    monkeypatch.setattr(
        "reflex_django.integration.install_reflex_django_integration",
        install_mock,
    )
    # Force the legacy Reflex-led code path. Without this the command takes
    # the DJANGO_OUTER branch, which spawns its own ASGI server instead of
    # invoking ``reflex run``. The handler imports ``resolve_url_routing``
    # lazily from :mod:`reflex_django.routing`, so we patch the source.
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.REFLEX_LED,
    )

    Command().handle(frontend_port="3005")

    install_mock.assert_called_once()
    assert captured_argv[:2] == ["reflex", "run"]
    assert "--frontend-port" in captured_argv
    assert "3005" in captured_argv
