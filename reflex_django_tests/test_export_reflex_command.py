"""Tests for the ``export_reflex`` management command."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from reflex_django.management.commands.export_reflex import Command


@pytest.fixture
def install_mock(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Patch ``install_reflex_django_integration`` and assert it runs first."""
    install = mock.MagicMock()
    monkeypatch.setattr(
        "reflex_django.integration.install_reflex_django_integration",
        install,
    )
    monkeypatch.setattr(
        "reflex_django.integration.refresh_get_config_bindings",
        mock.MagicMock(),
    )
    return install


@pytest.fixture
def export_mock(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Replace Reflex's heavy ``export_utils.export`` with a recorder."""
    export = mock.MagicMock()
    monkeypatch.setattr("reflex.utils.export.export", export)
    monkeypatch.setattr(
        "reflex.utils.prerequisites.assert_in_reflex_dir", mock.MagicMock()
    )
    return export


def test_export_reflex_invokes_reflex_export_utils(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
) -> None:
    """Default invocation (no flags) → frontend + backend, zipped, prod env."""
    Command().handle(
        env="prod",
        frontend_only=False,
        backend_only=False,
        no_zip=False,
        zip_dest_dir=str(Path.cwd()),
        ssr=True,
        stage_to_static_root=False,
        stage_target=None,
    )

    install_mock.assert_called_once()
    export_mock.assert_called_once()
    kwargs = export_mock.call_args.kwargs
    assert kwargs["frontend"] is True
    assert kwargs["backend"] is True
    assert kwargs["zipping"] is True
    assert kwargs["prerender_routes"] is True


def test_export_reflex_frontend_only_no_zip(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
) -> None:
    Command().handle(
        env="prod",
        frontend_only=True,
        backend_only=False,
        no_zip=True,
        zip_dest_dir=str(Path.cwd()),
        ssr=True,
        stage_to_static_root=False,
        stage_target=None,
    )

    install_mock.assert_called_once()
    kwargs = export_mock.call_args.kwargs
    assert kwargs["frontend"] is True
    assert kwargs["backend"] is False
    assert kwargs["zipping"] is False


def test_export_reflex_rejects_both_only_flags(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
) -> None:
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        Command().handle(
            env="prod",
            frontend_only=True,
            backend_only=True,
            no_zip=False,
            zip_dest_dir=str(Path.cwd()),
            ssr=True,
            stage_to_static_root=False,
            stage_target=None,
        )
    export_mock.assert_not_called()


def test_export_reflex_stages_to_explicit_target(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--stage-target`` copies the built SPA into the requested directory."""
    # Fake an exported ``.web/_static`` tree so the staging step can copy it.
    monkeypatch.chdir(tmp_path)
    build_dir = tmp_path / ".web" / "_static"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html>hi</html>", encoding="utf-8")
    (build_dir / "assets").mkdir()
    (build_dir / "assets" / "main.js").write_text("/* bundle */", encoding="utf-8")

    target = tmp_path / "out"

    Command().handle(
        env="prod",
        frontend_only=True,
        backend_only=False,
        no_zip=True,
        zip_dest_dir=str(tmp_path),
        ssr=True,
        stage_to_static_root=True,
        stage_target=str(target),
    )

    assert (target / "index.html").read_text(encoding="utf-8") == "<html>hi</html>"
    assert (target / "assets" / "main.js").is_file()


def test_export_reflex_stages_from_ssr_build_layout(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSR-enabled Reflex builds land in ``.web/build/client/`` — must stage from there.

    Newer Reflex (with SSR on by default) writes the client bundle into
    ``.web/build/client/index.html`` plus pre-rendered route HTML files
    (``about.html``, ``items.html``, ``__spa-fallback.html``, …) alongside
    it. Older logic only looked at ``.web/_static`` and ``.web/build``,
    which silently broke for SSR builds with the error the user hit:
    "Could not locate the built SPA directory".
    """
    monkeypatch.chdir(tmp_path)
    client = tmp_path / ".web" / "build" / "client"
    client.mkdir(parents=True)
    (client / "index.html").write_text("<html>root</html>", encoding="utf-8")
    (client / "about.html").write_text("<html>about</html>", encoding="utf-8")
    (client / "__spa-fallback.html").write_text("<html>fb</html>", encoding="utf-8")
    (client / "assets").mkdir()
    (client / "assets" / "main-deadbeef.js").write_text("/* */", encoding="utf-8")

    target = tmp_path / "staged"

    Command().handle(
        env="prod",
        frontend_only=True,
        backend_only=False,
        no_zip=True,
        zip_dest_dir=str(tmp_path),
        ssr=True,
        stage_to_static_root=True,
        stage_target=str(target),
    )

    assert (target / "index.html").read_text(encoding="utf-8") == "<html>root</html>"
    assert (target / "about.html").read_text(encoding="utf-8") == "<html>about</html>"
    assert (target / "__spa-fallback.html").is_file()
    assert (target / "assets" / "main-deadbeef.js").is_file()


def test_export_reflex_prefers_ssr_layout_over_legacy(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both layouts exist, the SSR ``.web/build/client`` directory wins.

    Some users keep stale ``.web/_static`` from a previous no-SSR build.
    The staging step must pick the freshest layout (SSR) so the staged
    tree reflects the current build output.
    """
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / ".web" / "_static"
    legacy.mkdir(parents=True)
    (legacy / "index.html").write_text("<html>stale</html>", encoding="utf-8")

    client = tmp_path / ".web" / "build" / "client"
    client.mkdir(parents=True)
    (client / "index.html").write_text("<html>fresh</html>", encoding="utf-8")

    target = tmp_path / "staged"

    Command().handle(
        env="prod",
        frontend_only=True,
        backend_only=False,
        no_zip=True,
        zip_dest_dir=str(tmp_path),
        ssr=True,
        stage_to_static_root=True,
        stage_target=str(target),
    )

    assert (target / "index.html").read_text(encoding="utf-8") == "<html>fresh</html>"


def test_export_reflex_runs_integration_before_calling_export(
    install_mock: mock.MagicMock,
    export_mock: mock.MagicMock,
) -> None:
    """The bug: ``reflex export`` directly fails with ``rxconfig.py not found``.

    Our wrapper must install the integration first so the synthetic
    ``rxconfig`` is in place by the time Reflex's export utility runs.
    """
    call_order: list[str] = []

    install_mock.side_effect = lambda: call_order.append("install")
    export_mock.side_effect = lambda **_: call_order.append("export")

    Command().handle(
        env="prod",
        frontend_only=True,
        backend_only=False,
        no_zip=True,
        zip_dest_dir=".",
        ssr=True,
        stage_to_static_root=False,
        stage_target=None,
    )

    assert call_order == ["install", "export"]
