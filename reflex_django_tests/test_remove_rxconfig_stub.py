"""Tests for removing auto-generated rxconfig.py stubs."""

from __future__ import annotations

from pathlib import Path

import pytest

from reflex_django.setup.rxconfig_bridge import (
    ensure_rxconfig_file,
    remove_django_first_rxconfig_stub,
)


def test_for_cli_does_not_write_rxconfig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text("# manage\n", encoding="utf-8")

    from django.conf import settings

    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", False, raising=False)

    assert ensure_rxconfig_file(for_cli=True) is None
    assert not (tmp_path / "rxconfig.py").is_file()


def test_remove_stub_leaves_user_rxconfig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manage.py").write_text("# manage\n", encoding="utf-8")
    (tmp_path / "rxconfig.py").write_text(
        "import reflex as rx\nconfig = rx.Config(app_name='mine')\n",
        encoding="utf-8",
    )

    from django.conf import settings

    monkeypatch.setattr(settings, "REFLEX_DJANGO_MATERIALIZE_RXCONFIG", False, raising=False)

    assert remove_django_first_rxconfig_stub() is False
    assert (tmp_path / "rxconfig.py").is_file()
