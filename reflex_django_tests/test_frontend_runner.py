"""Tests for the Vite frontend runner (``reflex_django.dev.runners.frontend``)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import reflex_django.dev.runners.frontend as _frontend_runner


def test_parse_argv_defaults() -> None:
    """No flags: watching on, compile-only off, port from --frontend-port."""
    args = _frontend_runner._parse_argv(["--frontend-port", "3210"])

    assert args.frontend_port == 3210
    assert args.compile_only is False
    assert args.compile_and_build is False
    assert args.watch is True
    assert args.skip_compile is False


def test_parse_argv_no_watch_and_compile_only() -> None:
    """``--no-watch`` and ``--compile-only`` flip their respective flags."""
    args = _frontend_runner._parse_argv(
        ["--frontend-port", "3000", "--no-watch", "--compile-only"]
    )

    assert args.frontend_port == 3000
    assert args.watch is False
    assert args.compile_only is True


def test_compile_and_build_compiles_and_builds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--compile-and-build`` bootstraps and runs the Reflex disk bundle pipeline."""
    bootstrap = mock.MagicMock()
    build_disk = mock.MagicMock()

    monkeypatch.setattr(_frontend_runner, "_bootstrap_integration", bootstrap)
    monkeypatch.setattr(
        _frontend_runner, "_apply_persistent_frontend_port", mock.MagicMock()
    )
    monkeypatch.setattr(_frontend_runner, "build_frontend_disk_bundle", build_disk)

    rc = _frontend_runner.main(["--compile-and-build"])

    assert rc == 0
    bootstrap.assert_called_once()
    build_disk.assert_called_once_with(compile_first=True)


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


def test_skip_compile_skips_compile_but_writes_env_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--skip-compile`` starts Vite without recompiling (parent already did)."""
    monkeypatch.setattr(
        _frontend_runner, "_bootstrap_integration", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_apply_persistent_frontend_port", mock.MagicMock()
    )
    compile_once = mock.MagicMock()
    write_env = mock.MagicMock()
    monkeypatch.setattr(_frontend_runner, "_compile_once_safe", compile_once)
    monkeypatch.setattr(_frontend_runner, "_write_env_json", write_env)
    monkeypatch.setattr(
        _frontend_runner, "_start_watch_thread", mock.MagicMock()
    )
    monkeypatch.setattr(
        _frontend_runner, "_run_vite", mock.MagicMock(return_value=0)
    )

    _frontend_runner.main(["--frontend-port", "3000", "--skip-compile"])

    compile_once.assert_not_called()
    write_env.assert_called_once()


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


def test_compile_app_for_frontend_syncs_vite_proxy_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After compile, Vite proxy layout is synced (strip in two-port dev)."""
    import reflex.utils.prerequisites as prerequisites

    monkeypatch.setattr(prerequisites, "compile_or_validate_app", mock.MagicMock())
    monkeypatch.setattr(_frontend_runner, "_write_env_json", mock.MagicMock())
    monkeypatch.setattr(
        "reflex_django.dev.frontend_stability.apply_frontend_stability_after_compile",
        mock.MagicMock(),
    )
    sync_layout = mock.MagicMock()
    monkeypatch.setattr(_frontend_runner, "_sync_vite_proxy_layout_after_compile", sync_layout)

    _frontend_runner._compile_app_for_frontend()

    sync_layout.assert_called_once()


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
        "reflex_django.dev.frontend_stability.apply_frontend_stability_after_compile",
        stability,
    )

    _frontend_runner._compile_app_for_frontend()

    compile_or_validate.assert_called_once()
    write_env.assert_called_once()
    stability.assert_called_once()


def test_build_id_for_disk_bundle_uses_compile_stamp_when_no_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    web = tmp_path / ".web"
    web.mkdir()
    env = web / "env.json"
    env.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "reflex_django.views.mount._resolve_spa_index",
        lambda: None,
    )
    monkeypatch.setattr(
        "reflex.utils.prerequisites.get_web_dir",
        lambda: web,
    )
    token = _frontend_runner.build_id_for_disk_bundle()
    assert token.startswith("compile:")


def test_build_frontend_client_bundle_uses_reflex_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = mock.MagicMock()
    run_export = mock.MagicMock()
    finalize = mock.MagicMock()
    ensure_dev = mock.MagicMock()
    backup = mock.MagicMock()
    clear_backup = mock.MagicMock()
    web_dir = mock.MagicMock()
    static_dir = mock.MagicMock()
    index = mock.MagicMock()
    index.is_file.return_value = True
    static_dir.__truediv__ = mock.MagicMock(return_value=index)
    web_dir.__truediv__ = mock.MagicMock(return_value=static_dir)

    monkeypatch.setattr(_frontend_runner, "_ensure_dev_env_mode", ensure_dev)
    monkeypatch.setattr(_frontend_runner, "_backup_client_bundle_before_build", backup)
    monkeypatch.setattr(_frontend_runner, "_clear_compile_dev_client_backup", clear_backup)
    monkeypatch.setattr(_frontend_runner, "_run_compile_dev_frontend_export", run_export)
    monkeypatch.setattr(_frontend_runner, "_finalize_reflex_client_build", finalize)
    monkeypatch.setattr(
        "reflex.utils.prerequisites.get_web_dir",
        lambda: web_dir,
    )
    monkeypatch.setattr(
        "reflex.utils.build.setup_frontend",
        setup,
    )

    _frontend_runner.build_frontend_client_bundle()

    ensure_dev.assert_called_once()
    backup.assert_called_once()
    setup.assert_called_once()
    run_export.assert_called_once()
    finalize.assert_called_once_with(compress=False)
    clear_backup.assert_called_once()


def test_compile_dev_reload_script_ignores_missing() -> None:
    from reflex_django.mount.spa_template import compile_dev_reload_script

    script = compile_dev_reload_script(wait_for_ready=False)
    assert "id!=='missing'" in script
    assert "last!==null&&id!==last" in script


def test_resolve_spa_index_falls_back_to_compile_dev_backup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """While ``.web/build`` is wiped, the previous client bundle remains servable."""
    from django.conf import settings

    from reflex_django.dev.runners.frontend import COMPILE_DEV_CLIENT_BACKUP_DIRNAME
    from reflex_django.views.mount import _resolve_spa_index

    web = tmp_path / ".web"
    backup = web / COMPILE_DEV_CLIENT_BACKUP_DIRNAME
    backup.mkdir(parents=True)
    (backup / "index.html").write_text("<html>backup</html>", encoding="utf-8")

    monkeypatch.setattr(settings, "BASE_DIR", tmp_path, raising=False)
    monkeypatch.setenv("REFLEX_DJANGO_COMPILE_DEV", "1")
    monkeypatch.chdir(tmp_path)

    index = _resolve_spa_index()
    assert index is not None
    assert index.read_text(encoding="utf-8") == "<html>backup</html>"
