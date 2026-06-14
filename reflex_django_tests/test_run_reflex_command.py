"""Tests for the simplified run_reflex management command."""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.management.base import CommandError

from reflex_django.management.commands.run_reflex import Command, _parse_asgi_target


def test_parse_asgi_target_django_dotted_path() -> None:
    assert _parse_asgi_target("base.asgi.application") == ("base.asgi", "application")


def test_parse_asgi_target_uvicorn_colon_path() -> None:
    assert _parse_asgi_target("base.asgi:application") == ("base.asgi", "application")


def _stub_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "reflex_django.runtime.integration.install_reflex_django_integration",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.runtime.integration.refresh_get_config_bindings",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.mount.auto.refresh_reflex_mount_catchall",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.dev.vite_proxy.ensure_vite_django_dev_proxy_from_config",
        mock.MagicMock(),
    )


def test_run_reflex_works_without_proxy_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    monkeypatch.delenv("RX_PROXY_SERVER", raising=False)
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle()

    invoke.assert_called_once()


def test_run_reflex_invokes_full_reflex_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    monkeypatch.setenv("RX_PROXY_SERVER", "http://127.0.0.1:8000")
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle(frontend_port="3005", backend_port="8010")

    invoke.assert_called_once()
    options = invoke.call_args.args[0]
    assert not options.get("frontend_only")
    assert not options.get("backend_only")


def test_from_build_runs_reflex_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    export_call = mock.MagicMock()
    invoke = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle(from_build=True, skip_rebuild=False)

    export_call.assert_called_once()
    invoke.assert_called_once()


def test_env_prod_runs_reflex_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    export_call = mock.MagicMock()
    invoke = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle(env="prod", skip_rebuild=True)

    invoke.assert_called_once()
    assert not export_call.called