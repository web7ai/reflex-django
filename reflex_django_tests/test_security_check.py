"""Tests for :mod:`reflex_django.setup.security_check`."""

from __future__ import annotations

from unittest import mock

from django.test import override_settings

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.setup import security_check  # noqa: E402


@override_settings(
    RX_AUTO_SETTINGS=True,
    DEBUG=True,
    ALLOWED_HOSTS=["*"],
    SESSION_COOKIE_HTTPONLY=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
def test_collects_all_insecure_defaults() -> None:
    issues = security_check.collect_insecure_default_warnings()
    blob = " ".join(issues).lower()
    assert "debug is true" in blob
    assert "allowed_hosts" in blob
    assert "session_cookie_httponly" in blob
    assert "session_cookie_secure" in blob
    assert "csrf_cookie_secure" in blob


@override_settings(
    RX_AUTO_SETTINGS=False,
    DEBUG=False,
    ALLOWED_HOSTS=["example.com"],
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
)
def test_no_warnings_when_hardened() -> None:
    assert security_check.collect_insecure_default_warnings() == []


@override_settings(DEBUG=True)
def test_warn_skips_in_dev() -> None:
    security_check._reset_warned_for_tests()
    with mock.patch("reflex_base.utils.console.warn") as warn:
        emitted = security_check.warn_insecure_defaults(env_name="dev")
    assert emitted is False
    warn.assert_not_called()


@override_settings(
    DEBUG=True,
    RX_AUTO_SETTINGS=True,
    ALLOWED_HOSTS=["*"],
)
def test_warn_fires_for_explicit_prod_env() -> None:
    security_check._reset_warned_for_tests()
    with mock.patch("reflex_base.utils.console.warn") as warn:
        emitted = security_check.warn_insecure_defaults(env_name="prod")
    assert emitted is True
    assert warn.called


@override_settings(DEBUG=False, ALLOWED_HOSTS=["*"])
def test_warn_is_one_shot() -> None:
    security_check._reset_warned_for_tests()
    with mock.patch("reflex_base.utils.console.warn"):
        first = security_check.warn_insecure_defaults()
        second = security_check.warn_insecure_defaults()
    assert first is True
    assert second is False
