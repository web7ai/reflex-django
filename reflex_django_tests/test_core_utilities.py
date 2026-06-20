"""Unit tests for Phase 0 shared utilities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from reflex_django.core.constants import (
    DEFAULT_BACKEND_PORT,
    DEFAULT_FRONTEND_PORT,
    RESERVED_REFLEX_PREFIXES,
)
from reflex_django.core.env import (
    setting_or_env_bool,
    truthy_env,
    truthy_env_or_none,
)
from reflex_django.core.users import username_str
from reflex_django.dev.process_utils import terminate_process
from reflex_django.mount.spa_paths import resolve_build_dir


def test_reserved_prefixes_include_event_and_upload():
    assert "/_event" in RESERVED_REFLEX_PREFIXES
    assert "/_upload" in RESERVED_REFLEX_PREFIXES


def test_default_ports():
    assert DEFAULT_FRONTEND_PORT == 3000
    assert DEFAULT_BACKEND_PORT == 8000


def test_truthy_env_parses_common_values():
    with mock.patch.dict(os.environ, {"TEST_FLAG": "1"}):
        assert truthy_env("TEST_FLAG") is True
    with mock.patch.dict(os.environ, {"TEST_FLAG": "false"}):
        assert truthy_env("TEST_FLAG") is False
    with mock.patch.dict(os.environ, {}, clear=True):
        assert truthy_env("MISSING", default=True) is True


def test_truthy_env_or_none_returns_none_when_unset():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert truthy_env_or_none("MISSING") is None


def test_setting_or_env_bool_prefers_env():
    with mock.patch.dict(os.environ, {"RX_SERVE_FROM_BUILD": "1"}):
        assert setting_or_env_bool(
            "RX_SERVE_FROM_BUILD",
            "RX_SERVE_FROM_BUILD",
            default=False,
        )


def test_username_str_uses_get_username():
    user = SimpleNamespace(get_username=lambda: "alice")
    assert username_str(user) == "alice"


def test_username_str_falls_back_to_username_attr():
    user = SimpleNamespace(username="bob")
    assert username_str(user) == "bob"


def test_terminate_process_noop_for_none():
    terminate_process(None)


def test_terminate_process_kills_running_proc():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        terminate_process(proc, timeout=0.5)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_resolve_build_dir_finds_index(tmp_path: Path):
    client = tmp_path / ".web" / "build" / "client"
    client.mkdir(parents=True)
    (client / "index.html").write_text("<html></html>", encoding="utf-8")
    assert resolve_build_dir(cwd=tmp_path) == client
