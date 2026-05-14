"""Tests for ``reflex_django.asgi.build_django_asgi``.

Covers the conditional wrapping with ``ASGIStaticFilesHandler`` so admin
CSS/JS load correctly when running under Reflex's granian server (which
replaces ``django runserver``).
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from reflex_django import asgi as asgi_module


@pytest.fixture
def fake_django_app() -> Any:
    """A sentinel ASGI app that ``get_asgi_application`` returns.

    Returns:
        A ``Mock`` instance the tests use as the stand-in Django ASGI app so
        we can assert it gets wrapped (or not) by ``ASGIStaticFilesHandler``
        without booting the real Django stack.
    """
    return mock.Mock(name="django_asgi")


def _patch_get_asgi_application(monkeypatch: pytest.MonkeyPatch, app: Any) -> None:
    """Stub Django's ``get_asgi_application`` and ``configure_django``."""
    monkeypatch.setattr(asgi_module, "configure_django", lambda: "stub")
    monkeypatch.setattr("django.core.asgi.get_asgi_application", lambda: app)


def test_build_django_asgi_wraps_with_static_handler_when_enabled(
    monkeypatch: pytest.MonkeyPatch, fake_django_app: Any
) -> None:
    """``django.contrib.staticfiles`` in INSTALLED_APPS → wrap with handler."""
    _patch_get_asgi_application(monkeypatch, fake_django_app)
    fake_settings = mock.Mock(INSTALLED_APPS=["django.contrib.staticfiles"])
    monkeypatch.setattr("django.conf.settings", fake_settings)

    handler_class = mock.Mock(name="ASGIStaticFilesHandler")
    monkeypatch.setattr(
        "django.contrib.staticfiles.handlers.ASGIStaticFilesHandler",
        handler_class,
    )

    result = asgi_module.build_django_asgi()

    handler_class.assert_called_once_with(fake_django_app)
    assert result is handler_class.return_value


def test_build_django_asgi_returns_bare_app_when_staticfiles_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_django_app: Any
) -> None:
    """Without staticfiles installed, return the raw ASGI app unwrapped."""
    _patch_get_asgi_application(monkeypatch, fake_django_app)
    fake_settings = mock.Mock(INSTALLED_APPS=["django.contrib.auth"])
    monkeypatch.setattr("django.conf.settings", fake_settings)

    handler_class = mock.Mock(name="ASGIStaticFilesHandler")
    monkeypatch.setattr(
        "django.contrib.staticfiles.handlers.ASGIStaticFilesHandler",
        handler_class,
    )

    result = asgi_module.build_django_asgi()

    handler_class.assert_not_called()
    assert result is fake_django_app


def test_build_django_asgi_calls_configure_first(
    monkeypatch: pytest.MonkeyPatch, fake_django_app: Any
) -> None:
    """``configure_django`` must run before ``get_asgi_application`` is called."""
    order: list[str] = []
    monkeypatch.setattr(
        asgi_module, "configure_django", lambda: order.append("configured")
    )

    def _get_asgi():
        order.append("get_asgi")
        return fake_django_app

    monkeypatch.setattr("django.core.asgi.get_asgi_application", _get_asgi)
    monkeypatch.setattr("django.conf.settings", mock.Mock(INSTALLED_APPS=[]))

    asgi_module.build_django_asgi()

    assert order == ["configured", "get_asgi"]
