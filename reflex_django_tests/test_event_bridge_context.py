"""Event bridge attaches context processors to the synthetic request."""

from __future__ import annotations

from unittest import mock

from django.test import RequestFactory

from reflex_django.conf import configure_django

configure_django()

from reflex_django.context import get_request_reflex_context  # noqa: E402
from reflex_django.middleware import _attach_reflex_context  # noqa: E402


async def test_attach_reflex_context_caches_on_request(monkeypatch) -> None:
    merged = {"site_name": "Demo"}

    async def _fake_collect(request):  # noqa: ANN001
        return merged

    monkeypatch.setattr(
        "reflex_django.reflex_context.reflex_context_processor_paths",
        lambda: ("fake.proc",),
    )
    monkeypatch.setattr(
        "reflex_django.reflex_context.collect_reflex_context",
        _fake_collect,
    )

    request = RequestFactory().get("/")
    await _attach_reflex_context(request)
    assert get_request_reflex_context(request) == merged
