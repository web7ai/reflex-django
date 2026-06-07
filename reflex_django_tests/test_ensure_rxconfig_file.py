"""Tests for materializing rxconfig.py in Django-first mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from reflex_django.mount_config import clear_mount_rx_config, register_mount_rx_config
from reflex_django.rxconfig_bridge import ensure_rxconfig_file


@pytest.fixture(autouse=True)
def _clear_mount() -> None:
    clear_mount_rx_config()
    yield
    clear_mount_rx_config()


def test_ensure_rxconfig_file_writes_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )

    from django.conf import settings

    register_mount_rx_config(app_name="myfrontend")
    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", True, raising=False)

    created = ensure_rxconfig_file()
    assert created is not None
    assert (tmp_path / "rxconfig.py").is_file()
    text = (tmp_path / "rxconfig.py").read_text(encoding="utf-8")
    assert 'app_name="myfrontend"' in text or "app_name='myfrontend'" in text
    assert "app_module_import='reflex_django.reflex_app'" in text

    assert ensure_rxconfig_file() is None


def test_ensure_rxconfig_file_uses_project_folder_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    (project_dir / "manage.py").write_text("# manage\n", encoding="utf-8")

    from django.conf import settings

    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", True, raising=False)

    created = ensure_rxconfig_file()
    assert created is not None
    text = (project_dir / "rxconfig.py").read_text(encoding="utf-8")
    assert 'app_name="my_project"' in text or "app_name='my_project'" in text


def test_ensure_rxconfig_file_updates_stale_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )
    (tmp_path / "rxconfig.py").write_text(
        "import reflex as rx\nconfig = rx.Config(app_name='wrong')\n",
        encoding="utf-8",
    )

    from django.conf import settings

    register_mount_rx_config(app_name="demo")
    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", False, raising=False)

    assert ensure_rxconfig_file() is None

    from reflex_django.rxconfig_bridge import is_django_first_rxconfig_stub

    (tmp_path / "rxconfig.py").write_text(
        '"""Stub ``rxconfig`` for reflex-django Django-first mode."""\n'
        "import reflex as rx\nconfig = rx.Config(app_name='wrong')\n",
        encoding="utf-8",
    )
    assert is_django_first_rxconfig_stub(tmp_path / "rxconfig.py")

    assert ensure_rxconfig_file(for_cli=True) is None
    text = (tmp_path / "rxconfig.py").read_text(encoding="utf-8")
    assert "app_name='wrong'" in text

    from reflex_django.rxconfig_bridge import remove_django_first_rxconfig_stub

    assert remove_django_first_rxconfig_stub() is True
    assert not (tmp_path / "rxconfig.py").is_file()
