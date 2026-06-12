"""Tests for manage.py discovery."""

from __future__ import annotations

import sys
import textwrap
import types
from pathlib import Path

import pytest

from reflex_django.setup.project import (
    RXCONFIG_SYNTHETIC_ATTR,
    discover_settings_module,
    find_manage_py,
    parse_settings_module,
    rxconfig_module_has_file,
)


def test_parse_settings_module_setdefault(tmp_path: Path) -> None:
    manage = tmp_path / "manage.py"
    manage.write_text(
        textwrap.dedent(
            """
            import os
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
            """
        ),
        encoding="utf-8",
    )
    assert parse_settings_module(manage) == "myproject.settings"


def test_parse_settings_module_assign(tmp_path: Path) -> None:
    manage = tmp_path / "manage.py"
    manage.write_text(
        'import os\nos.environ["DJANGO_SETTINGS_MODULE"] = "shop.settings"\n',
        encoding="utf-8",
    )
    assert parse_settings_module(manage) == "shop.settings"


def test_discover_settings_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_path / "app"
    sub.mkdir()
    manage = tmp_path / "manage.py"
    manage.write_text(
        'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(sub)
    assert discover_settings_module() == "app.settings"


def test_find_manage_py_walks_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    nested = root / "pkg" / "inner"
    nested.mkdir(parents=True)
    (root / "manage.py").write_text("# manage\n", encoding="utf-8")
    monkeypatch.chdir(nested)
    assert find_manage_py() == root / "manage.py"


def test_rxconfig_module_has_file_ignores_synthetic_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from reflex_django.setup.project import rxconfig_path

    monkeypatch.setattr(
        "reflex_django.setup.project.rxconfig_path",
        lambda *args, **kwargs: None,
    )
    stub = types.ModuleType("rxconfig")
    setattr(stub, RXCONFIG_SYNTHETIC_ATTR, True)
    monkeypatch.setitem(sys.modules, "rxconfig", stub)
    assert rxconfig_module_has_file() is False
