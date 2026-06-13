"""Tests for Django-first dev reload path resolution."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.runtime.app_factory import _APP_MODULE_STUB_MARKER
from reflex_django.runtime.integration import (
    install_reflex_django_integration,
    reset_integration_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_integration() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_rx_config()


def test_reload_paths_watch_django_project_not_reflex_django_package(
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
    register_mount_rx_config(app_name="myapp")

    install_reflex_django_integration()

    from reflex_base.config import get_config
    from reflex.utils.exec import get_reload_paths
    from reflex.utils.prerequisites import _check_app_name

    cfg = get_config()
    assert cfg.app_module_import == "myapp.myapp"
    assert cfg.module == "myapp.myapp"

    stub = project / "myapp" / "myapp.py"
    assert stub.is_file()
    assert _APP_MODULE_STUB_MARKER in stub.read_text(encoding="utf-8")

    _check_app_name(cfg)

    app_mod = importlib.import_module("myapp.myapp")
    assert app_mod.app is not None

    reload_paths = [p.resolve() for p in get_reload_paths()]
    assert shop.resolve() in reload_paths

    reflex_pkg_root = (
        Path(importlib.import_module("reflex_django.runtime.reflex_app").__file__)
        .resolve()
        .parent.parent
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
