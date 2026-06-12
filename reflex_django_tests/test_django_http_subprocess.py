"""Tests for Django HTTP subprocess lifecycle helpers."""

from __future__ import annotations

from unittest import mock

import pytest

import reflex_django.asgi.http_subprocess as subproc


@pytest.fixture(autouse=True)
def _reset_proc(monkeypatch: pytest.MonkeyPatch) -> None:
    subproc._django_http_proc = None
    subproc._spawned_by_us = False
    monkeypatch.delenv("REFLEX_DJANGO_HTTP_UPSTREAM", raising=False)
    monkeypatch.delenv("REFLEX_DJANGO_HTTP_SUBPROCESS", raising=False)
    yield
    subproc.terminate_django_http_subprocess()


def test_resolve_django_http_upstream_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_HTTP_UPSTREAM", "http://127.0.0.1:9001")
    assert subproc.resolve_django_http_upstream() == "http://127.0.0.1:9001"


def test_resolve_django_http_upstream_default_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_HTTP_PORT", "8010")
    assert subproc.resolve_django_http_upstream() == "http://127.0.0.1:8010"


def test_spawn_and_terminate_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_proc = mock.Mock()
    fake_proc.poll.return_value = None
    fake_proc.wait.return_value = 0

    monkeypatch.setattr(
        "reflex_django.asgi.http_subprocess.subprocess.Popen",
        lambda *a, **k: fake_proc,
    )

    proc = subproc.spawn_django_http_subprocess(port=8011)
    assert proc is fake_proc
    assert subproc._spawned_by_us is True

    subproc.terminate_django_http_subprocess()
    fake_proc.terminate.assert_called_once()
    assert subproc._django_http_proc is None


def test_ensure_upstream_ready_when_already_listening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFLEX_DJANGO_HTTP_UPSTREAM", "http://127.0.0.1:8001")
    monkeypatch.setattr(
        "reflex_django.asgi.http_subprocess._tcp_reachable",
        lambda *_a, **_k: True,
    )
    spawn = mock.Mock()
    monkeypatch.setattr(subproc, "spawn_django_http_subprocess", spawn)

    upstream = subproc.ensure_django_http_upstream_ready()
    assert upstream == "http://127.0.0.1:8001"
    spawn.assert_not_called()


def test_wait_until_ready_detects_exited_subprocess() -> None:
    fake_proc = mock.Mock()
    fake_proc.poll.return_value = 1
    subproc._django_http_proc = fake_proc

    assert subproc.wait_until_ready("http://127.0.0.1:8001", timeout=0.2) is False
