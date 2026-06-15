"""Tests for plugin Reflex CLI layout bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from reflex_django.runtime.integration import (
    install_reflex_django_integration,
    reset_integration_for_tests,
)
from reflex_django.mount.config import clear_mount_registration


@pytest.fixture(autouse=True)
def _reset() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_registration()


def test_plugin_rxconfig_loads_from_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rxconfig = tmp_path / "rxconfig.py"
    rxconfig.write_text(
        'import reflex as rx\n'
        'from reflex_django.plugins import ReflexDjangoPlugin\n'
        'config = rx.Config(\n'
        '    app_name="demo",\n'
        '    frontend_port=3000,\n'
        '    plugins=[ReflexDjangoPlugin(config={"settings_module": "reflex_django_tests.django_settings", "auto_mount": False})],\n'
        ')\n',
        encoding="utf-8",
    )
    (tmp_path / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
    if "rxconfig" in sys.modules:
        del sys.modules["rxconfig"]

    try:
        from reflex_base.config import get_config
        from reflex_django.runtime.integration.detect import detect_reflex_django_plugin

        install_reflex_django_integration()
        config = get_config(reload=True)
        assert config.app_name == "demo"
        assert detect_reflex_django_plugin(config) is not None
        assert rxconfig.is_file()
        assert "rxconfig" in sys.modules
        assert getattr(sys.modules["rxconfig"], "config", None) is not None
    finally:
        sys.path.remove(str(tmp_path))
