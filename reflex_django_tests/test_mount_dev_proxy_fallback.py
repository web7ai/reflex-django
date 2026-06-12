"""Tests for ReflexMountView dev-proxy loop guard and disk fallback."""

from __future__ import annotations

import asyncio
import os
from unittest import mock

import pytest

from reflex_django.views import mount


@pytest.fixture(autouse=True)
def _isolate_dev_proxy_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the self-loop latch and dev-proxy env so tests don't bleed.

    ``_disable_dev_proxy_after_self_loop`` mutates a module-level flag and
    ``os.environ`` directly; snapshot and restore both around each test.
    """
    monkeypatch.setattr(mount, "_dev_proxy_self_loop_handled", False, raising=False)
    monkeypatch.setattr(mount, "_vite_unreachable_until", 0.0, raising=False)
    monkeypatch.setattr(mount, "_vite_unreachable_logged", False, raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_DEV_PROXY", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_SEPARATE_DEV_PORTS", raising=False)


class _FakeRequest:
    def __init__(self, port: str, path: str = "/favicon.ico") -> None:
        self._port = port
        self.path = path

    def get_port(self) -> str:
        return self._port

    def get_host(self) -> str:
        return f"localhost:{self._port}"


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.mark.parametrize(
    ("target", "req_port", "expected"),
    [
        ("http://127.0.0.1:3000", "3000", True),
        ("http://localhost:3000", "3000", True),
        ("http://0.0.0.0:3000", "3000", True),
        ("http://127.0.0.1:3000", "8000", False),
        ("http://10.0.0.5:3000", "3000", False),
        ("http://127.0.0.1", "3000", False),
    ],
)
def test_dev_proxy_target_is_self(
    target: str, req_port: str, expected: bool
) -> None:
    """Same host:port as the inbound request is treated as a self-proxy."""
    request = _FakeRequest(port=req_port)
    assert mount._dev_proxy_target_is_self(request, target) is expected


def _patch_common(monkeypatch: pytest.MonkeyPatch) -> dict[str, mock.MagicMock]:
    """Patch the collaborators of ``_handle`` and return them."""
    serve = mock.MagicMock(return_value=_FakeResponse(200))
    monkeypatch.setattr(mount, "_serve_spa_response", serve)
    monkeypatch.setattr(
        mount, "maybe_render_spa_html", lambda _req, resp: resp
    )
    return {"serve": serve}


def test_self_target_serves_from_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A self-pointing Vite target falls back to the disk bundle (no loop)."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    proxy = mock.AsyncMock()
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="3000")

    asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_not_called()
    patched["serve"].assert_called_once_with("/favicon.ico")


def test_self_loop_disables_dev_proxy_process_wide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Detecting a self-loop sets REFLEX_DJANGO_DEV_PROXY=0 to stop re-checking."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", mock.AsyncMock())

    view = mount.ReflexMountView()
    asyncio.run(view._handle(_FakeRequest(port="3000")))  # type: ignore[arg-type]

    assert os.environ.get("REFLEX_DJANGO_DEV_PROXY") == "0"
    assert mount._dev_proxy_self_loop_handled is True


def test_proxy_502_falls_back_to_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Vite is unreachable (502) the view serves the disk bundle."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    proxy = mock.AsyncMock(return_value=_FakeResponse(502))
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")  # different port -> not self

    asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_awaited_once()
    patched["serve"].assert_called_once_with("/favicon.ico")


def test_second_request_during_cooldown_skips_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a 502, a follow-up request serves disk without re-probing Vite."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    proxy = mock.AsyncMock(return_value=_FakeResponse(502))
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")  # not self

    # First request probes Vite (502) and arms the cooldown.
    asyncio.run(view._handle(request))  # type: ignore[arg-type]
    # Second request is inside the cooldown -> no second probe.
    asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_awaited_once()
    assert patched["serve"].call_count == 2


def test_cooldown_logs_warning_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated outages within one episode warn a single time."""
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    monkeypatch.setattr(
        mount, "reverse_proxy_to_vite", mock.AsyncMock(return_value=_FakeResponse(502))
    )
    # Force the cooldown to be expired so every request re-probes.
    monkeypatch.setattr(mount, "_VITE_UNREACHABLE_COOLDOWN_S", 0.0)
    warnings: list[str] = []
    monkeypatch.setattr(
        mount.logger, "warning", lambda msg, *a, **k: warnings.append(msg)
    )

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")
    asyncio.run(view._handle(request))  # type: ignore[arg-type]
    asyncio.run(view._handle(request))  # type: ignore[arg-type]

    assert len(warnings) == 1


def test_healthy_proxy_response_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reachable Vite (200) is used directly; no disk fallback."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    ok = _FakeResponse(200)
    proxy = mock.AsyncMock(return_value=ok)
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")

    result = asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_awaited_once()
    patched["serve"].assert_not_called()
    assert result is ok


def test_proxy_502_returns_503_when_dev_proxy_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When REFLEX_DJANGO_DEV_PROXY=1, a 502 does not fall back to disk."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setenv("REFLEX_DJANGO_DEV_PROXY", "1")
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    proxy = mock.AsyncMock(return_value=_FakeResponse(502))
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")

    result = asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_awaited_once()
    patched["serve"].assert_not_called()
    assert result.status_code == 503


def test_separate_ports_returns_plain_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-port dev: stray SPA paths on the backend port get a plain 404."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setattr("reflex_django.views.mount.dev_uses_separate_ports", lambda: True)
    monkeypatch.setattr(mount, "_dev_vite_target_or_none", lambda: None)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000", path="/login")

    result = asyncio.run(view._handle(request))  # type: ignore[arg-type]

    patched["serve"].assert_not_called()
    assert result.status_code == 404
    assert not result.content


def test_cooldown_returns_503_when_dev_proxy_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cooldown skips disk fallback when dev proxy is explicitly on."""
    patched = _patch_common(monkeypatch)
    monkeypatch.setenv("REFLEX_DJANGO_DEV_PROXY", "1")
    monkeypatch.setattr(
        mount, "_dev_vite_target_or_none", lambda: "http://127.0.0.1:3000"
    )
    proxy = mock.AsyncMock(return_value=_FakeResponse(502))
    monkeypatch.setattr(mount, "reverse_proxy_to_vite", proxy)

    view = mount.ReflexMountView()
    request = _FakeRequest(port="8000")

    asyncio.run(view._handle(request))  # type: ignore[arg-type]
    result = asyncio.run(view._handle(request))  # type: ignore[arg-type]

    proxy.assert_awaited_once()
    patched["serve"].assert_not_called()
    assert result.status_code == 503
