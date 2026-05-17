"""Tests for :mod:`reflex_django.session_js`."""

from __future__ import annotations

from reflex_django.conf import configure_django

configure_django()

from reflex_django.session_js import (  # noqa: E402
    session_cookie_clear_js,
    session_cookie_name_and_suffix,
    session_cookie_set_js,
)


def test_session_cookie_clear_uses_same_attributes_as_set() -> None:
    _, attrs = session_cookie_name_and_suffix()
    clear = session_cookie_clear_js()
    set_js = session_cookie_set_js("abc123")
    assert attrs in clear
    assert attrs in set_js
    assert "max-age=0" in clear


def test_session_cookie_set_escapes_quotes() -> None:
    js = session_cookie_set_js("a'b\\c")
    assert "a\\'b\\\\c" in js
