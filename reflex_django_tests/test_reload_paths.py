"""Tests for plugin dev reload path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from reflex_django.mount.config import clear_mount_registration
from reflex_django.runtime.integration import (
    install_bootstrap_patches,
    reset_integration_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_registration()


def test_plugin_reload_paths_watch_django_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "myproject"
    shop = project / "shop"
    shop.mkdir(parents=True)
    (shop / "views.py").write_text("# pages\n", encoding="utf-8")
    (project / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(project)
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")

    from django.conf import settings

    monkeypatch.setattr(settings, "BASE_DIR", project, raising=False)

    install_bootstrap_patches(patch_get_config=False)

    from reflex_django.dev.watch import plugin_reload_paths

    reload_paths = [p.resolve() for p in plugin_reload_paths()]
    assert shop.resolve() in reload_paths

    reflex_pkg_root = (
        Path(__import__("reflex_django").__file__).resolve().parent
    )
    assert reflex_pkg_root not in reload_paths


def test_resolve_dev_watch_roots_uses_base_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from django.conf import settings

    from reflex_django.dev.watch import resolve_dev_watch_roots

    monkeypatch.setattr(settings, "BASE_DIR", tmp_path, raising=False)
    monkeypatch.chdir(tmp_path)

    roots = resolve_dev_watch_roots()
    assert tmp_path.resolve() in roots
