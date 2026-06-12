"""Reflex config loaded from Django without rxconfig.py on disk."""

from __future__ import annotations

import sys

import pytest
from django.conf import settings


def test_ensure_rxconfig_from_django_without_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", '
        '"reflex_django_tests.django_settings")\n',
        encoding="utf-8",
    )
    from reflex_django.mount.config import register_mount_rx_config

    register_mount_rx_config(
        app_name="myfrontend",
        rx_config={"frontend_port": 3000},
    )
    monkeypatch.setattr(settings, "INSTALLED_APPS", [*settings.INSTALLED_APPS, "reflex_django"], raising=False)
    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", False, raising=False)
    monkeypatch.setattr(settings, "REFLEX_DJANGO_USE_RXCONFIG_FILE", False, raising=False)

    assert not (tmp_path / "rxconfig.py").is_file()

    from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django

    config = ensure_rxconfig_from_django()
    assert config.app_name == "myfrontend"
    assert config.frontend_port == 3000
    assert sys.modules["rxconfig"].config is config
    assert not (tmp_path / "rxconfig.py").is_file()
