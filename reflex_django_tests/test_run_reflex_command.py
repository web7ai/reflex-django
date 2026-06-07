"""Tests for the run_reflex management command."""

from __future__ import annotations

import sys
from unittest import mock

import pytest

from reflex_django.management.commands.run_reflex import Command
from reflex_django.routing import UrlRoutingMode


def test_run_reflex_invokes_reflex_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run_reflex`` delegates to ``reflex run`` for legacy and default dev paths."""
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
    monkeypatch.setattr(
        "reflex_django.integration.refresh_get_config_bindings",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.auto_mount.refresh_reflex_mount_catchall",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.DJANGO_OUTER,
    )

    Command().handle(frontend_port="3005")

    install_mock.assert_called_once()
    assert captured_argv[:2] == ["reflex", "run"]
    assert "--frontend-port" in captured_argv
    assert "3005" in captured_argv


# ---------------------------------------------------------------------------
# --from-build flag (auto-export + serve-from-disk in dev)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_compile_frontend(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Mock the frontend compiler to prevent real Node build execution in tests."""
    compile_mock = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django._frontend_runner._compile_app_for_frontend",
        compile_mock,
    )
    return compile_mock


@pytest.fixture
def _stub_asgi_server(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Replace ``_run_asgi_server`` and ``_run_with_watch_reload`` with no-ops.

    We do not want the test to actually start uvicorn (which blocks forever)
    or open a real :mod:`watchfiles` watcher (which also blocks). The fixture
    returns the ``_run_asgi_server`` mock since most tests exercise the
    non-reload code path; tests that need to assert on the watch loop should
    patch ``_run_with_watch_reload`` separately.
    """
    server = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_asgi_server",
        server,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_with_watch_reload",
        mock.MagicMock(),
    )
    return server


@pytest.fixture
def _force_django_outer_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the routing mode to DJANGO_OUTER for these tests."""
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.DJANGO_OUTER,
    )
    monkeypatch.setattr(
        "reflex_django.integration.install_reflex_django_integration",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.integration.refresh_get_config_bindings",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.auto_mount.refresh_reflex_mount_catchall",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        mock.MagicMock(),
    )
    # Avoid real TCP port checks / Vite boot waits when the host has :3000 busy.
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._ensure_frontend_port_free",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._wait_for_vite_ready",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._compile_dev_app_once",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._start_vite_ready_notifier",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_vite_background",
        mock.MagicMock(return_value=mock.Mock(poll=lambda: None)),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_uvicorn_dev_subprocess",
        mock.MagicMock(return_value=mock.Mock(poll=lambda: None)),
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._supervise_vite_dev_procs",
        mock.MagicMock(),
    )


def test_from_build_triggers_export_and_disables_vite_proxy(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
    _stub_compile_frontend: mock.MagicMock,
) -> None:
    """``--from-build`` exports the SPA to ``.web`` AND sets REFLEX_DJANGO_DEV_PROXY=0."""
    export_call = mock.MagicMock()
    monkeypatch.setattr(
        "django.core.management.call_command", export_call
    )
    # Don't spawn a real Vite child.
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_vite_background",
        mock.MagicMock(),
    )
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)

    from django.conf import settings
    monkeypatch.setattr(settings, "STATIC_ROOT", "/static", raising=False)

    Command().handle(from_build=True, skip_rebuild=False)

    export_call.assert_called_once()
    name, *_ = export_call.call_args.args
    assert name == "export_reflex"
    assert export_call.call_args.kwargs.get("env") == "dev"
    assert export_call.call_args.kwargs.get("stage_to_static_root") is False
    _stub_compile_frontend.assert_not_called()

    # Dev-proxy explicitly turned off so the catch-all view serves from disk.
    import os

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_from_build_skip_rebuild_does_not_re_export(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
    _stub_compile_frontend: mock.MagicMock,
) -> None:
    """``--from-build --skip-rebuild`` uses the existing bundle on disk."""
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)

    Command().handle(from_build=True, skip_rebuild=True)

    export_call.assert_not_called()
    _stub_compile_frontend.assert_not_called()
    # Still flips the dev-proxy off so the user gets the disk SPA.
    import os

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_setting_serve_from_build_implies_from_build(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
    _stub_compile_frontend: mock.MagicMock,
) -> None:
    """``settings.REFLEX_DJANGO_SERVE_FROM_BUILD = True`` enables the flag globally.

    Saves users from passing ``--from-build`` on every command invocation.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_SERVE_FROM_BUILD", raising=False)

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", True, raising=False
    )

    Command().handle()

    export_call.assert_called_once()
    name, *_ = export_call.call_args.args
    assert name == "export_reflex"
    assert export_call.call_args.kwargs.get("env") == "dev"
    assert export_call.call_args.kwargs.get("stage_to_static_root") is False
    _stub_compile_frontend.assert_not_called()


def test_from_build_does_not_spawn_vite(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--from-build`` must not spawn a Vite child process."""
    monkeypatch.setattr("django.core.management.call_command", mock.MagicMock())
    vite_spawn = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_vite_background",
        vite_spawn,
    )

    Command().handle(from_build=True, skip_rebuild=True)

    vite_spawn.assert_not_called()


def test_env_prod_always_exports(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env prod`` always auto-exports.

    Auto-export compiles the SPA on boot and stages it into STATIC_ROOT/_reflex.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spa_index_missing",
        lambda self: False,
    )

    Command().handle(env="prod")

    export_call.assert_called_once()
    import os

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_env_prod_builds_spa_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env prod`` with no bundle on disk builds it once so the run works.

    This is the fix for "Reflex SPA bundle not found" on a fresh local
    ``run_reflex --env prod``: rather than 404, we auto-export + stage the
    SPA before serving.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spa_index_missing",
        lambda self: True,
    )
    # Avoid the post-build warning path importing the real view repeatedly.
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._warn_if_spa_missing",
        mock.MagicMock(),
    )

    from django.conf import settings
    monkeypatch.setattr(settings, "STATIC_ROOT", "/static", raising=False)

    Command().handle(env="prod")

    export_call.assert_called_once()
    name, *_ = export_call.call_args.args
    assert name == "export_reflex"
    assert export_call.call_args.kwargs.get("env") == "prod"
    assert export_call.call_args.kwargs.get("stage_to_static_root") is True


def test_env_prod_skip_rebuild_never_builds(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env prod --skip-rebuild`` never builds, even if the bundle is gone."""
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spa_index_missing",
        lambda self: True,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._warn_if_spa_missing",
        mock.MagicMock(),
    )

    Command().handle(env="prod", skip_rebuild=True)

    export_call.assert_not_called()


def test_env_prod_always_exports_and_does_not_reload(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env prod`` always auto-exports, but does NOT run the reload loop.

    Even if settings.REFLEX_DJANGO_SERVE_FROM_BUILD = True or reload is enabled
    in dev, production remains a non-reload serve-from-disk run.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    watch_reload = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_with_watch_reload",
        watch_reload,
    )

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", True, raising=False
    )

    Command().handle(env="prod")

    export_call.assert_called_once()
    watch_reload.assert_not_called()


def test_from_build_setting_enables_export_without_flag(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
    _stub_compile_frontend: mock.MagicMock,
) -> None:
    """Setting ``REFLEX_DJANGO_SERVE_FROM_BUILD = True`` opts into from-build.

    Vite is the default now, but a project that explicitly turns the setting
    on gets the serve-from-disk loop without passing ``--from-build`` on every
    invocation — the export runs automatically before serving.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_SERVE_FROM_BUILD", raising=False)

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", True, raising=False
    )

    Command().handle()  # no flags at all

    export_call.assert_called_once()
    name, *_ = export_call.call_args.args
    assert name == "export_reflex"
    assert export_call.call_args.kwargs.get("env") == "dev"
    assert export_call.call_args.kwargs.get("stage_to_static_root") is False
    _stub_compile_frontend.assert_not_called()
    import os

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_with_vite_opts_out_of_from_build(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--with-vite`` overrides ``REFLEX_DJANGO_SERVE_FROM_BUILD=True``.

    Users who want the legacy Vite-HMR loop pass ``--with-vite`` (alias
    ``--no-from-build``); we must skip the auto-export AND delegate to
    ``reflex run``.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", True, raising=False
    )

    Command().handle(with_vite=True)

    export_call.assert_not_called()
    invoke.assert_called_once()


def test_from_build_uses_parent_watch_reload(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
) -> None:
    """``--from-build`` (with reload on) routes through ``_run_with_watch_reload``.

    This is the bug-fix verification: uvicorn's in-process reloader is
    disabled in from-build mode because re-importing the ASGI app re-runs
    the reflex-django bootstrap and never re-exports the SPA. The parent
    watch loop is the only mechanism that triggers an auto-export between
    reloads.
    """
    asgi_server = mock.MagicMock()
    watch_reload = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_asgi_server",
        asgi_server,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_with_watch_reload",
        watch_reload,
    )
    monkeypatch.setattr(
        "django.core.management.call_command", mock.MagicMock()
    )

    Command().handle(from_build=True)

    watch_reload.assert_called_once()
    asgi_server.assert_not_called()
    # The watch loop receives the skip_rebuild flag so the per-restart
    # re-export can be suppressed for fast Python-only iterations.
    assert watch_reload.call_args.kwargs.get("skip_rebuild") is False


def test_no_reload_in_from_build_uses_plain_asgi_server(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
) -> None:
    """``--from-build --no-reload`` skips the watch loop entirely.

    A one-shot rebuild + serve (no auto-restart) is what CI smoke tests
    want, and what ``--env prod`` already does. ``--no-reload`` lets the
    user opt into that same one-shot semantics in dev.
    """
    asgi_server = mock.MagicMock()
    watch_reload = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_asgi_server",
        asgi_server,
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_with_watch_reload",
        watch_reload,
    )
    monkeypatch.setattr(
        "django.core.management.call_command", mock.MagicMock()
    )

    Command().handle(from_build=True, no_reload=True)

    watch_reload.assert_not_called()
    asgi_server.assert_called_once()
    assert asgi_server.call_args.kwargs.get("reload") is False


def test_explicit_from_build_beats_with_vite(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
    _stub_compile_frontend: mock.MagicMock,
) -> None:
    """If the user passes both ``--from-build`` and ``--with-vite`` (silly), the
    explicit ``--from-build`` wins.

    Asserting the precedence in tests so a future refactor doesn't silently
    swap which flag wins.
    """
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    vite_spawn = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_vite_background",
        vite_spawn,
    )

    Command().handle(from_build=True, with_vite=True)

    export_call.assert_called_once()
    name, *_ = export_call.call_args.args
    assert name == "export_reflex"
    assert export_call.call_args.kwargs.get("env") == "dev"
    _stub_compile_frontend.assert_not_called()
    vite_spawn.assert_not_called()


# ---------------------------------------------------------------------------
# Vite is the default dev loop now (REFLEX_DJANGO_SERVE_FROM_BUILD defaults False)
# ---------------------------------------------------------------------------


def test_default_spawns_vite_and_skips_export(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """Plain ``run_reflex`` (no flags) delegates to ``reflex run`` without export."""
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )
    monkeypatch.delenv("REFLEX_DJANGO_SERVE_FROM_BUILD", raising=False)

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", False, raising=False
    )

    Command().handle()  # no flags at all

    invoke.assert_called_once()
    export_call.assert_not_called()


def test_vite_default_two_port_dev_proxy_off(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """Default two-port dev sets DEV_PROXY=0 and SEPARATE_DEV_PORTS=1."""
    monkeypatch.setattr("django.core.management.call_command", mock.MagicMock())
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_SEPARATE_DEV_PORTS", raising=False)

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", False, raising=False
    )

    Command().handle()

    import os

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"
    assert os.environ.get("REFLEX_DJANGO_SEPARATE_DEV_PORTS") == "1"


def test_vite_default_delegates_to_reflex_run(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """Default Vite dev calls ``_invoke_reflex_run`` instead of manual subprocesses."""
    monkeypatch.setattr("django.core.management.call_command", mock.MagicMock())
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", False, raising=False
    )

    Command().handle()

    invoke.assert_called_once()


def test_frontend_only_in_dev_spawns_vite_blocking_with_watch(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """frontend_only in dev spawns blocking Vite with watch thread, bypassing reflex run."""
    spawn_vite_blocking = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_vite_blocking",
        spawn_vite_blocking,
    )
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    from django.conf import settings
    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", False, raising=False
    )

    # test watch=True
    Command().handle(frontend_only=True)
    assert spawn_vite_blocking.call_count == 1
    assert isinstance(spawn_vite_blocking.call_args[0][0], int)
    assert spawn_vite_blocking.call_args[1].get("watch") is True
    invoke.assert_not_called()

    # test watch=False with no_reload
    spawn_vite_blocking.reset_mock()
    Command().handle(frontend_only=True, no_reload=True)
    assert spawn_vite_blocking.call_count == 1
    assert isinstance(spawn_vite_blocking.call_args[0][0], int)
    assert spawn_vite_blocking.call_args[1].get("watch") is False
    invoke.assert_not_called()



def test_env_prod_sets_separate_dev_ports_off(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env prod`` must not leave two-port mode on so the SPA serves from disk."""
    monkeypatch.setattr("django.core.management.call_command", mock.MagicMock())
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spa_index_missing",
        lambda self: False,
    )
    monkeypatch.delenv("REFLEX_DJANGO_SEPARATE_DEV_PORTS", raising=False)

    Command().handle(env="prod")

    import os

    assert os.environ.get("REFLEX_DJANGO_SEPARATE_DEV_PORTS") == "0"
    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"


def test_dev_proxy_explicit_env_overrides_settings_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``REFLEX_DJANGO_DEV_PROXY=1`` wins over settings False."""
    from django.conf import settings

    from reflex_django.dev_proxy import _dev_vite_target_or_none

    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(settings, "REFLEX_DJANGO_DEV_PROXY", False, raising=False)
    monkeypatch.setenv("REFLEX_DJANGO_DEV_PROXY", "1")
    monkeypatch.setenv("REFLEX_DJANGO_SEPARATE_DEV_PORTS", "0")
    monkeypatch.setenv("REFLEX_DJANGO_FRONTEND_PORT", "3000")

    assert _dev_vite_target_or_none() == "http://127.0.0.1:3000"


def test_default_compiles_in_parent_and_starts_vite_with_skip_compile(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """Default dev delegates compile + Vite boot to ``reflex run``."""
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle()

    invoke.assert_called_once()


def test_no_reload_sets_backend_reload_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_reflex --no-reload`` disables backend reload via env for ``reflex run``."""
    import os

    cli_mock = mock.MagicMock()
    cli_mock.commands = {"run": mock.MagicMock()}
    cli_mock.main = mock.MagicMock()

    import reflex.reflex as reflex_module

    monkeypatch.setattr(reflex_module, "cli", cli_mock)
    monkeypatch.delenv("REFLEX_DJANGO_BACKEND_RELOAD", raising=False)

    Command()._invoke_reflex_run({"no_reload": True})

    assert os.environ.get("REFLEX_DJANGO_BACKEND_RELOAD") == "0"
    cli_mock.main.assert_called_once()


# ---------------------------------------------------------------------------
# reflex run backend patch (DJANGO_OUTER)
# ---------------------------------------------------------------------------


def _reset_backend_patch_flag() -> None:
    import reflex.utils.exec as exec_module

    if hasattr(exec_module, "_reflex_django_run_backend_patched"):
        exec_module._reflex_django_run_backend_patched = False


def test_patched_uvicorn_backend_uses_asgi_entry_with_reload_excludes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev backend with Vite spawns ``_backend_runner`` (Windows-safe subprocess)."""
    _reset_backend_patch_flag()
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.DJANGO_OUTER,
    )

    spawn = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.integration._spawn_django_outer_backend_subprocess",
        spawn,
    )
    monkeypatch.setattr(
        "reflex.utils.exec.should_use_granian",
        lambda: False,
    )
    monkeypatch.setattr(
        "reflex.utils.exec.get_web_dir",
        lambda: mock.Mock(exists=lambda: False),
    )

    from reflex_django.integration import install_reflex_django_integration
    import reflex.utils.exec as exec_module

    install_reflex_django_integration()

    import os

    os.environ.pop("REFLEX_DJANGO_BACKEND_RELOAD", None)
    os.environ["REFLEX_DJANGO_FRONTEND_PRESENT"] = "1"
    exec_module.run_backend("0.0.0.0", 8000, frontend_present=True)

    spawn.assert_called_once()
    assert spawn.call_args.kwargs.get("reload") is True


def test_patched_uvicorn_backend_inprocess_without_frontend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend-only dev uses in-process uvicorn on the main thread."""
    _reset_backend_patch_flag()
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.DJANGO_OUTER,
    )

    uvicorn_run = mock.MagicMock()
    monkeypatch.setattr("uvicorn.run", uvicorn_run)
    monkeypatch.setattr(
        "reflex.utils.exec.get_reload_paths",
        lambda: ["/project"],
    )
    monkeypatch.setattr(
        "reflex.utils.exec.should_use_granian",
        lambda: False,
    )
    monkeypatch.setattr(
        "reflex.utils.exec.get_web_dir",
        lambda: mock.Mock(exists=lambda: False),
    )
    monkeypatch.setattr(
        "reflex.utils.exec.notify_backend",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.integration._spawn_django_outer_backend_subprocess",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django.integration.sys.platform",
        "linux",
    )

    from reflex_django.integration import install_reflex_django_integration
    import reflex.utils.exec as exec_module

    install_reflex_django_integration()

    import os

    os.environ.pop("REFLEX_DJANGO_BACKEND_RELOAD", None)
    os.environ.pop("REFLEX_DJANGO_FRONTEND_PRESENT", None)
    exec_module.run_backend("0.0.0.0", 8000, frontend_present=False)

    uvicorn_run.assert_called_once()
    kwargs = uvicorn_run.call_args.kwargs
    assert kwargs["app"] == "reflex_django.asgi_entry:application"
    assert kwargs["reload"] is True


def test_patched_uvicorn_backend_honors_no_reload_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``REFLEX_DJANGO_BACKEND_RELOAD=0`` disables uvicorn reload."""
    _reset_backend_patch_flag()
    monkeypatch.setattr(
        "reflex_django.routing.resolve_url_routing",
        lambda: UrlRoutingMode.DJANGO_OUTER,
    )

    spawn = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.integration._spawn_django_outer_backend_subprocess",
        spawn,
    )
    monkeypatch.setattr(
        "reflex.utils.exec.should_use_granian",
        lambda: False,
    )
    monkeypatch.setattr(
        "reflex.utils.exec.get_web_dir",
        lambda: mock.Mock(exists=lambda: False),
    )
    monkeypatch.setattr(
        "reflex.utils.exec.notify_backend",
        mock.MagicMock(),
    )

    from reflex_django.integration import install_reflex_django_integration
    import reflex.utils.exec as exec_module

    install_reflex_django_integration()

    import os

    os.environ["REFLEX_DJANGO_BACKEND_RELOAD"] = "0"
    os.environ["REFLEX_DJANGO_FRONTEND_PRESENT"] = "1"
    exec_module.run_backend("0.0.0.0", 8000, frontend_present=True)

    spawn.assert_called_once()
    assert spawn.call_args.kwargs.get("reload") is False


def test_backend_runner_passes_reload_excludes_when_vite_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uvicorn_run = mock.MagicMock()
    monkeypatch.setattr("uvicorn.run", uvicorn_run)
    monkeypatch.setattr(
        "reflex_django.integration.install_reflex_django_integration",
        mock.MagicMock(),
    )
    monkeypatch.setattr(
        "reflex_django._backend_runner._resolve_watch_root",
        lambda: "/project",
    )

    import os

    os.environ["REFLEX_DJANGO_FRONTEND_PRESENT"] = "1"
    os.environ.pop("REFLEX_DJANGO_BACKEND_RELOAD", None)
    monkeypatch.setattr("reflex_django._backend_runner.sys.platform", "linux")

    from reflex_django._backend_runner import main

    main(["--host", "127.0.0.1", "--port", "8000"])

    kwargs = uvicorn_run.call_args.kwargs
    assert kwargs["app"] == "reflex_django.asgi_entry:application"
    assert kwargs["reload"] is True
    assert kwargs.get("reload_excludes")


def test_invoke_reflex_run_clears_unused_ports_in_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_invoke_reflex_run clears unused ports in config for frontend/backend only runs."""
    captured_get_config_backend_port = 8000
    captured_get_config_frontend_port = 3000

    def mock_main(*args, **kwargs):
        nonlocal captured_get_config_backend_port, captured_get_config_frontend_port
        import reflex_base.config as config_module
        cfg = config_module.get_config()
        captured_get_config_backend_port = cfg.backend_port
        captured_get_config_frontend_port = cfg.frontend_port

    cli_mock = mock.MagicMock()
    cli_mock.commands = {"run": mock.MagicMock()}
    cli_mock.main = mock_main

    import reflex.reflex as reflex_module
    monkeypatch.setattr(reflex_module, "cli", cli_mock)

    class MockConfig:
        def __init__(self):
            self.frontend_port = 3000
            self.backend_port = 8000

    mock_config = MockConfig()
    rxconfig_mock = mock.Mock()
    rxconfig_mock.config = mock_config
    monkeypatch.setitem(sys.modules, "rxconfig", rxconfig_mock)

    # Mock original get_config to return our mock_config
    import reflex_base.config as config_module
    monkeypatch.setattr(config_module, "get_config", lambda *a, **k: mock_config)

    # Test frontend_only resets backend_port
    Command()._invoke_reflex_run({"frontend_only": True})
    assert mock_config.backend_port is None
    assert mock_config.frontend_port == 3000
    assert captured_get_config_backend_port is None
    assert captured_get_config_frontend_port == 3000

    # Reset and test backend_only resets frontend_port
    mock_config.backend_port = 8000
    mock_config.frontend_port = 3000
    Command()._invoke_reflex_run({"backend_only": True})
    assert mock_config.frontend_port is None
    assert mock_config.backend_port == 8000
    assert captured_get_config_frontend_port is None
    assert captured_get_config_backend_port == 8000


def test_env_dev_compiles_to_web_with_single_port_compile_dev(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
    _stub_asgi_server: mock.MagicMock,
) -> None:
    """``--env dev`` compiles to ``.web/`` only; no ``react-router build`` per save."""
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    compile_disk = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._compile_dev_once",
        compile_disk,
    )
    start_recompile_watch = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django._frontend_runner.start_compile_dev_watch",
        start_recompile_watch,
    )
    spawn_uvicorn = mock.MagicMock(
        return_value=mock.Mock(poll=lambda: None, wait=mock.MagicMock())
    )
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._spawn_uvicorn_dev_subprocess",
        spawn_uvicorn,
    )
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    from django.conf import settings

    monkeypatch.setattr(
        settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", True, raising=False
    )

    Command().handle(env="dev")

    export_call.assert_not_called()
    compile_disk.assert_called_once()
    start_recompile_watch.assert_called_once()
    spawn_uvicorn.assert_called_once()
    assert spawn_uvicorn.call_args.kwargs.get("reload") is False
    invoke.assert_not_called()
    import os

    assert os.environ.get("REFLEX_DJANGO_COMPILE_DEV") == "1"
    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"
    assert os.environ.get("REFLEX_DJANGO_SEPARATE_DEV_PORTS") == "0"


def test_env_dev_with_vite_opts_out(
    monkeypatch: pytest.MonkeyPatch,
    _force_django_outer_mode: None,
) -> None:
    """``--env dev --with-vite`` runs the native two-port ``reflex run`` loop."""
    export_call = mock.MagicMock()
    monkeypatch.setattr("django.core.management.call_command", export_call)
    watch_reload = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._run_with_watch_reload",
        watch_reload,
    )
    invoke = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.management.commands.run_reflex.Command._invoke_reflex_run",
        invoke,
    )

    Command().handle(env="dev", with_vite=True)

    export_call.assert_not_called()
    watch_reload.assert_not_called()
    invoke.assert_called_once()
