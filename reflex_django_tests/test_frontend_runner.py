"""Tests for the Vite frontend runner (``reflex_django._frontend_runner``)."""

from __future__ import annotations

from unittest import mock

import pytest

from reflex_django import _frontend_runner


def test_parse_argv_defaults() -> None:
    """No flags: watching on, compile-only off, port from --frontend-port."""
    args = _frontend_runner._parse_argv(["--frontend-port", "3210"])

    assert args.frontend_port == 3210
    assert args.compile_only is False
    assert args.watch is True


def test_parse_argv_no_watch_and_compile_only() -> None:
    """``--no-watch`` and ``--compile-only`` flip their respective flags."""
    args = _frontend_runner._parse_argv(
        ["--frontend-port", "3000", "--no-watch", "--compile-only"]
    )

    assert args.frontend_port == 3000
    assert args.watch is False
    assert args.compile_only is True


def test_compile_only_compiles_and_skips_vite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--compile-only`` bootstraps + compiles, but never starts Vite/watcher."""
    bootstrap = mock.MagicMock()
    apply_port = mock.MagicMock()
    compile_app = mock.MagicMock()
    run_vite = mock.MagicMock()
    start_watch = mock.MagicMock()

    monkeypatch.setattr(_frontend_runner, "_bootstrap_integration", bootstrap)
    monkeypatch.setattr(
        _frontend_runner, "_apply_persistent_frontend_port", apply_port
    )
    monkeypatch.setattr(
        _frontend_runner, "_compile_app_for_frontend", compile_app
    )
    monkeypatch.setattr(_frontend_runner, "_run_vite", run_vite)
    monkeypatch.setattr(_frontend_runner, "_start_watch_thread", start_watch)

    rc = _frontend_runner.main(["--frontend-port", "3000", "--compile-only"])

    assert rc == 0
    bootstrap.assert_called_once()
    compile_app.assert_called_once()
    run_vite.assert_not_called()
    start_watch.assert_not_called()


def test_default_mode_starts_watch_then_vite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default mode compiles once, starts the watch thread, then runs Vite."""
    monkeypatch.setattr(
        _frontend_runner, "_bootstrap_integration", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_apply_persistent_frontend_port", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_compile_app_for_frontend", mock.MagicMock()
    )
    start_watch = mock.MagicMock()
    run_vite = mock.MagicMock(return_value=0)
    monkeypatch.setattr(_frontend_runner, "_start_watch_thread", start_watch)
    monkeypatch.setattr(_frontend_runner, "_run_vite", run_vite)

    rc = _frontend_runner.main(["--frontend-port", "3000"])

    assert rc == 0
    start_watch.assert_called_once_with(3000)
    run_vite.assert_called_once_with(3000)


def test_no_watch_skips_watch_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-watch`` runs Vite without starting the recompile watch thread."""
    monkeypatch.setattr(
        _frontend_runner, "_bootstrap_integration", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_apply_persistent_frontend_port", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_compile_app_for_frontend", mock.MagicMock()
    )
    start_watch = mock.MagicMock()
    monkeypatch.setattr(_frontend_runner, "_start_watch_thread", start_watch)
    monkeypatch.setattr(
        _frontend_runner, "_run_vite", mock.MagicMock(return_value=0)
    )

    _frontend_runner.main(["--frontend-port", "3000", "--no-watch"])

    start_watch.assert_not_called()


def test_write_env_json_invokes_reflex_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_write_env_json`` writes ``.web/env.json`` via reflex's ``set_env_json``.

    Vite's generated ``.web/utils/state.js`` imports ``$/env.json``; without
    this file Vite fails with ``Cannot find module '$/env.json'``.
    """
    import reflex.utils.build as build

    set_env = mock.MagicMock()
    monkeypatch.setattr(build, "set_env_json", set_env)

    _frontend_runner._write_env_json()

    set_env.assert_called_once()


def test_write_env_json_swallows_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure writing env.json is downgraded to a warning, not a crash."""
    import reflex.utils.build as build

    monkeypatch.setattr(
        build,
        "set_env_json",
        mock.MagicMock(side_effect=RuntimeError("boom")),
    )

    # Must not raise.
    _frontend_runner._write_env_json()


def test_compile_app_for_frontend_applies_stability_patches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After compile, EventLoopContext guards are applied to generated ``.web`` files."""
    import reflex.utils.prerequisites as prerequisites

    compile_or_validate = mock.MagicMock()
    write_env = mock.MagicMock()
    stability = mock.MagicMock(return_value=["utils/context.js"])

    monkeypatch.setattr(prerequisites, "compile_or_validate_app", compile_or_validate)
    monkeypatch.setattr(_frontend_runner, "_write_env_json", write_env)
    monkeypatch.setattr(
        "reflex_django.frontend_stability.apply_frontend_stability_after_compile",
        stability,
    )

    _frontend_runner._compile_app_for_frontend()

    compile_or_validate.assert_called_once()
    write_env.assert_called_once()
    stability.assert_called_once()
