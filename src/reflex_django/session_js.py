"""Helpers for setting Django session cookies from Reflex ``rx.call_script``.

Cookies set via ``document.cookie`` cannot be ``HttpOnly``. For production,
prefer a Django view that returns ``Set-Cookie`` with ``HttpOnly`` and then
reload the Reflex app.
"""

from __future__ import annotations


def session_cookie_name_and_suffix() -> tuple[str, str]:
    """Return ``(cookie_name, attribute_suffix)`` for ``document.cookie`` writes.

    ``attribute_suffix`` is everything after ``name=value;`` (path, max-age,
    SameSite, Secure when enabled).

    Returns:
        Tuple of cookie name and formatted attribute suffix.
    """
    from django.conf import settings as django_settings

    name = getattr(django_settings, "SESSION_COOKIE_NAME", "sessionid")
    max_age = int(getattr(django_settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 14))
    path = getattr(django_settings, "SESSION_COOKIE_PATH", "/") or "/"
    samesite = getattr(django_settings, "SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
    secure = (
        "; secure" if getattr(django_settings, "SESSION_COOKIE_SECURE", False) else ""
    )
    domain = getattr(django_settings, "SESSION_COOKIE_DOMAIN", None)
    domain_part = f"; domain={domain}" if domain else ""
    return name, f"path={path}; max-age={max_age}; samesite={samesite}{secure}{domain_part}"


def session_cookie_set_js(session_key: str) -> str:
    """JavaScript snippet assigning the session cookie and value-escaping.

    Args:
        session_key: Raw session key from ``request.session.session_key``.

    Returns:
        A one-line JS expression suitable for ``rx.call_script``.
    """
    name, attrs = session_cookie_name_and_suffix()
    safe = session_key.replace("\\", "\\\\").replace("'", "\\'")
    return f"document.cookie = '{name}={safe}; {attrs}';"


def session_cookie_clear_js() -> str:
    """JavaScript snippet that expires the session cookie in the browser.

    Uses the same path/domain attributes as :func:`session_cookie_set_js` so a stale
    ``sessionid`` is removed before writing a new key after login.

    Returns:
        A one-line JS expression suitable for ``rx.call_script``.
    """
    name, attrs = session_cookie_name_and_suffix()
    return f"document.cookie = '{name}=; {attrs}; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';"


__all__ = [
    "session_cookie_clear_js",
    "session_cookie_name_and_suffix",
    "session_cookie_set_js",
]
