"""Tests for env.json frontend proxy patching."""

from __future__ import annotations

import json
from pathlib import Path

from reflex_django.dev.vite_proxy import patch_env_json_for_frontend_proxy


def test_patch_env_json_for_frontend_proxy(tmp_path: Path) -> None:
    env = tmp_path / "env.json"
    env.write_text(
        json.dumps(
            {
                "EVENT": "ws://localhost:8000/_event",
                "PING": "http://localhost:8000/ping",
            }
        ),
        encoding="utf-8",
    )
    assert patch_env_json_for_frontend_proxy(
        tmp_path,
        frontend_port=3000,
        backend_port=8000,
    )
    data = json.loads(env.read_text(encoding="utf-8"))
    assert data["EVENT"] == "ws://localhost:3000/_event"
    assert data["PING"] == "http://localhost:3000/ping"
