"""Tests for ``reflex_django.init_project``."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import click
import pytest

from reflex_django.init_project import run_reflex_django_init


def test_run_reflex_django_init_rejects_existing_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myapp").mkdir()
    with pytest.raises(click.ClickException, match="already exists"):
        run_reflex_django_init("myapp")


def test_run_reflex_django_init_calls_uv_sequence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[Path, tuple[str, ...]]] = []

    def fake_run_uv(root: Path, *args: str) -> None:
        calls.append((root, args))
        if args[:2] == ("run", "reflex"):
            (root / "rxconfig.py").write_text("config = None\n", encoding="utf-8")
            (root / "myapp").mkdir()
            (root / "myapp" / "myapp.py").write_text("# stub\n", encoding="utf-8")
        if args[:2] == ("run", "reflex-django"):
            pass

    monkeypatch.setattr("reflex_django.init_project._run_uv", fake_run_uv)
    monkeypatch.setattr(
        "reflex_django.init_project._validate_app_name", lambda name: name
    )

    root = run_reflex_django_init("myapp")

    assert root == tmp_path / "myapp"
    assert (root / "django_settings.py").is_file()
    assert (root / "myapp" / "__init__.py").is_file()
    assert (root / "README.md").is_file()
    assert (root / ".env.example").is_file()
    assert (root / "rxconfig.py").read_text(encoding="utf-8").count("ReflexDjangoPlugin")
    assert "LocaleMiddleware" in (root / "django_settings.py").read_text(encoding="utf-8")
    app_py = (root / "myapp" / "myapp.py").read_text(encoding="utf-8")
    assert "add_auth_pages" in app_py
    assert "DjangoAuthState" in app_py
    assert "routes.LOGIN_ROUTE" in app_py
    assert "install_event_bridge=True" in (root / "rxconfig.py").read_text(encoding="utf-8")
    assert any(c[1][:2] == ("init", "--name") for c in calls)
    assert any(c[1][:3] == ("add", "reflex>=0.9.2,<1.0") for c in calls)
    assert any(c[1][:2] == ("add", "reflex-django") for c in calls)
    assert any(
        c[1][:6] == ("run", "reflex", "init", "--template", "blank", "--name")
        for c in calls
    )
    assert any(c[1] == ("lock",) for c in calls)
    assert any(
        c[1][:4] == ("run", "reflex-django", "migrate", "--noinput") for c in calls
    )
