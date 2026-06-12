"""Tests for :mod:`reflex_django.bridge.session_js`."""

from __future__ import annotations

from reflex_django.setup.conf import configure_django

configure_django()

from reflex_django.bridge.session_js import (  # noqa: E402
    browser_auth_cookies_clear_js,
    session_cookie_clear_js,
    session_cookie_name_and_suffix,
    session_cookie_set_js,
)


def test_session_cookie_clear_uses_same_attributes_as_set() -> None:
    name, attrs = session_cookie_name_and_suffix()
    clear = session_cookie_clear_js()
    set_js = session_cookie_set_js("abc123")
    assert name in clear
    assert attrs.split(";")[0] in set_js or "path=" in clear
    assert "max-age=0" in clear


def test_session_cookie_set_escapes_quotes() -> None:
    js = session_cookie_set_js("a'b\\c")
    assert "a\\'b\\\\c" in js


def test_browser_auth_cookies_clear_includes_csrf() -> None:
    js = browser_auth_cookies_clear_js()
    assert "sessionid" in js
    assert "csrftoken" in js
