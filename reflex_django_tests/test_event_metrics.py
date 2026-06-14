"""Tests for opt-in event bridge metrics."""

from __future__ import annotations

import logging

import pytest
from django.conf import settings

from reflex_django.setup.conf import configure_django

configure_django()


def test_measure_event_phase_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from reflex_django.bridge.metrics import measure_event_phase

    monkeypatch.setattr(settings, "RX_EVENT_METRICS", False, raising=False)
    caplog.set_level(logging.DEBUG)

    with measure_event_phase("build"):
        pass

    assert not any("build" in r.message for r in caplog.records)


def test_measure_event_phase_logs_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from reflex_django.bridge.metrics import measure_event_phase

    monkeypatch.setattr(settings, "RX_EVENT_METRICS", True, raising=False)
    caplog.set_level(logging.DEBUG, logger="reflex_django.bridge.metrics")

    with measure_event_phase("resolve_user"):
        pass

    assert any("resolve_user" in r.message for r in caplog.records)
