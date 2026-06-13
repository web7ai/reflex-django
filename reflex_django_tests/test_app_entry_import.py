"""Tests that {app_name}/{app_name}.py runs on first bootstrap."""

from __future__ import annotations

import sys
import types

import pytest
from django.conf import settings

from reflex_django.mount.config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.runtime.app_factory import (
    get_or_create_app,
    import_app_entry_module,
    reflex_app_module_name,
    reset_app_factory_cache,
)

_APP_NAME = "entrytest"


@pytest.fixture(autouse=True)
def _reset_entry_import_state() -> None:
    clear_mount_rx_config()
    register_mount_rx_config(app_name=_APP_NAME)
    reset_app_factory_cache()
    yield
    reset_app_factory_cache()
    clear_mount_rx_config()
    sys.modules.pop(reflex_app_module_name(_APP_NAME), None)
    sys.modules.pop(_APP_NAME, None)


def _wire_tmp_project(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path, raising=False)
    monkeypatch.syspath_prepend(str(tmp_path))


def test_import_app_entry_module_replaces_synthetic_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    marker_path = tmp_path / "entry_ran.txt"
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        f'''"""Entry module side effects."""
from pathlib import Path
from reflex_django.runtime.reflex_app import app

Path({str(marker_path)!r}).write_text("ran", encoding="utf-8")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    module_name = reflex_app_module_name(_APP_NAME)
    synthetic = types.ModuleType(module_name)
    synthetic.app = object()
    sys.modules[module_name] = synthetic

    module = import_app_entry_module(app_name=_APP_NAME)

    assert marker_path.read_text(encoding="utf-8") == "ran"
    assert getattr(module, "__file__", None) == str(stub.resolve())
    assert module is sys.modules[module_name]
    assert module is not synthetic


def test_get_or_create_app_executes_entry_module_on_cold_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    package = tmp_path / _APP_NAME
    package.mkdir()
    marker_path = tmp_path / "cold_start_ran.txt"
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        f'''"""Entry module for cold-start bootstrap."""
from pathlib import Path
from reflex_django.runtime.reflex_app import app

Path({str(marker_path)!r}).write_text("cold", encoding="utf-8")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    module_name = reflex_app_module_name(_APP_NAME)
    synthetic = types.ModuleType(module_name)
    synthetic.app = object()
    sys.modules[module_name] = synthetic

    get_or_create_app()

    assert marker_path.read_text(encoding="utf-8") == "cold"
    loaded = sys.modules[module_name]
    assert getattr(loaded, "__file__", None) == str(stub.resolve())
    assert loaded is not synthetic


def test_reimport_after_bootstrap_uses_disk_module(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import importlib

    package = tmp_path / _APP_NAME
    package.mkdir()
    counter_path = tmp_path / "import_count.txt"
    counter_path.write_text("0", encoding="utf-8")
    stub = package / f"{_APP_NAME}.py"
    stub.write_text(
        f'''"""Entry module import counter."""
from pathlib import Path
from reflex_django.runtime.reflex_app import app

path = Path({str(counter_path)!r})
count = int(path.read_text(encoding="utf-8"))
path.write_text(str(count + 1), encoding="utf-8")
''',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("", encoding="utf-8")
    _wire_tmp_project(monkeypatch, tmp_path)

    get_or_create_app()
    assert counter_path.read_text(encoding="utf-8") == "1"

    importlib.reload(sys.modules[reflex_app_module_name(_APP_NAME)])
    assert counter_path.read_text(encoding="utf-8") == "2"
