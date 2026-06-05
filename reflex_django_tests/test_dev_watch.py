"""Tests for dev watch path classification."""

from __future__ import annotations

import os

from reflex_django.dev_watch import (
    backend_reload_excludes,
    is_backend_reload_path,
    is_frontend_recompile_path,
)


def test_settings_triggers_backend_not_frontend() -> None:
    path = os.path.join("base", "settings.py")
    assert is_backend_reload_path(path) is True
    assert is_frontend_recompile_path(path) is False


def test_state_triggers_backend_not_frontend() -> None:
    path = os.path.join(
        "modules", "ai", "studio", "pages", "retrieval", "state.py"
    )
    assert is_backend_reload_path(path) is True
    assert is_frontend_recompile_path(path) is False


def test_views_triggers_frontend_not_backend() -> None:
    path = os.path.join(
        "modules", "ai", "studio", "pages", "retrieval", "views.py"
    )
    assert is_frontend_recompile_path(path) is True
    assert is_backend_reload_path(path) is False


def test_backend_reload_excludes_views_and_shell() -> None:
    excludes = backend_reload_excludes()
    assert "**/views.py" in excludes
    assert "**/shell/**" in excludes


def test_shell_layout_triggers_frontend_only() -> None:
    shell = os.path.join("core", "shell", "theme.py")
    layout = os.path.join("modules", "ai", "studio", "layout", "template.py")
    assert is_frontend_recompile_path(shell) is True
    assert is_frontend_recompile_path(layout) is True
    assert is_backend_reload_path(shell) is False
