"""Tests for the simplified run_reflex management command."""

from __future__ import annotations

import sys
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


def test_run_reflex_frontend_only_invokes_frontend_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    frontend_runner = mock.MagicMock(return_value=0)
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_frontend_runner",
        frontend_runner,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle(frontend_only=True)

    frontend_runner.assert_called_once()
    assert not invoke.called
    options = frontend_runner.call_args.args[0]
    assert options.get("frontend_only")


def test_invoke_frontend_runner_forwards_no_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main = mock.MagicMock(return_value=0)
    monkeypatch.setattr(
        "reflex_django.dev.runners.frontend.main",
        main,
    )
    plan = mock.MagicMock(frontend_port=3005)

    Command()._invoke_frontend_runner({"no_reload": True}, plan)

    main.assert_called_once_with(["--frontend-port", "3005", "--no-watch"])


def test_invoke_frontend_runner_raises_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "reflex_django.dev.runners.frontend.main",
        mock.MagicMock(return_value=1),
    )
    plan = mock.MagicMock(frontend_port=3000)

    with pytest.raises(CommandError, match="Frontend dev server exited"):
        Command()._invoke_frontend_runner({}, plan)


def test_run_reflex_backend_only_invokes_reflex_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_integration(monkeypatch)
    invoke = mock.MagicMock()
    plain_django = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_plain_django",
        plain_django,
    )
    monkeypatch.setattr(
        "reflex_django.mount.auto.refresh_reflex_mount_catchall",
        mock.MagicMock(),
    )

    Command().handle(backend_only=True)

    invoke.assert_called_once()
    assert not plain_django.called
    options = invoke.call_args.args[0]
    assert options.get("backend_only")


def test_invoke_reflex_run_forwards_backend_only_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_argv: list[str] = []

    def capture_argv(*_args: object, **_kwargs: object) -> None:
        captured_argv.extend(sys.argv)

    monkeypatch.setattr(
        "reflex.reflex.cli.main",
        capture_argv,
    )
    monkeypatch.setattr(
        "reflex_django.runtime.integration._rebind_get_config_imports",
        mock.MagicMock(),
    )
    plan = mock.MagicMock(serve_from_disk=False, backend_port=8000)
    options = {
        "backend_only": True,
        "backend_port": "8010",
        "backend_host": "127.0.0.1",
        "loglevel": "info",
        "reflex_args": [],
    }

    Command()._invoke_reflex_run(options, plan)

    assert captured_argv == [
        "reflex",
        "run",
        "--backend-port",
        "8010",
        "--backend-host",
        "127.0.0.1",
        "--loglevel",
        "info",
        "--backend-only",
    ]


def test_run_uvicorn_passes_import_string_when_reload_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uvicorn_run = mock.MagicMock()
    monkeypatch.setattr("uvicorn.run", uvicorn_run)
    mock_module = mock.MagicMock()
    mock_module.application = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.asgi_helpers.importlib.import_module",
        lambda name: mock_module,
    )
    monkeypatch.setattr(
        "reflex_django.dev.watch.resolve_dev_watch_roots",
        lambda: [],
    )

    Command()._run_uvicorn(
        target="base.asgi.application",
        host="127.0.0.1",
        port=8000,
        loglevel="info",
        reload=True,
    )

    app_arg = uvicorn_run.call_args.args[0]
    assert app_arg == "base.asgi:application"
    assert not isinstance(app_arg, mock.MagicMock)
    assert uvicorn_run.call_args.kwargs["reload"] is True