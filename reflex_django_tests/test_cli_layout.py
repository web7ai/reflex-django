"""Tests for Django-first Reflex CLI layout bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from reflex_django.integration import (
    install_reflex_django_integration,
    reset_integration_for_tests,
)
from reflex_django.mount_config import clear_mount_rx_config, register_mount_rx_config


@pytest.fixture(autouse=True)
def _reset() -> None:
    yield
    reset_integration_for_tests()
    clear_mount_rx_config()


def test_needs_reinit_false_after_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")

    register_mount_rx_config(app_name="demo", rx_config={"frontend_port": 3000})

    install_reflex_django_integration()

    from reflex.utils import prerequisites

    assert prerequisites.needs_reinit() is False
    assert (tmp_path / "rxconfig.py").is_file()
