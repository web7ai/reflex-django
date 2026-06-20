"""Tests for configure_django settings discovery from manage.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

import reflex_django.setup.conf as conf_module
from reflex_django.setup.conf import configure_django


def test_configure_django_discovers_manage_py(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)

    (tmp_path / "manage.py").write_text(
        textwrap.dedent("""
            import os
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reflex_django_tests.django_settings")
            """),
        encoding="utf-8",
    )

    result = configure_django()
    assert result == "reflex_django_tests.django_settings"
