"""Helpers for setting Django session cookies from Reflex ``rx.call_script``.

Cookies set via ``document.cookie`` cannot be ``HttpOnly``. For production,
prefer a Django view that returns ``Set-Cookie`` with ``HttpOnly`` and then
reload the Reflex app.
"""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
from typing import Any


def _cookie_clear_js(
    name: str,
    *,
    path: str = "/",
    domain: str | None = None,
    samesite: str = "Lax",
    secure: bool = False,
) -> str:
    """JavaScript that expires a single named cookie in the browser."""
    domain_part = f"; domain={domain}" if domain else ""
    secure_part = "; secure" if secure else ""
    safe_name = name.replace("\\", "\\\\").replace("'", "\\'")
    return (
        f"document.cookie = '{safe_name}=; path={path}; max-age=0; "
        f"expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite={samesite}"
        f"{secure_part}{domain_part}';"
    )


def _cookie_clear_variants_js(
    name: str,
    *,
    path: str,
    domain: str | None,
    samesite: str,
    secure: bool,
) -> str:
    """Expire a cookie using several path/domain/secure combinations.

    Browsers keep cookies that were set with different attributes than a single
    ``max-age=0`` write uses, which is why logout sometimes leaves ``sessionid``.
    """
    attempts: list[str] = []
    seen: set[str] = set()

    def add(
        *, cookie_path: str, cookie_domain: str | None, cookie_secure: bool
    ) -> None:
        js = _cookie_clear_js(
            name,
            path=cookie_path,
            domain=cookie_domain,
            samesite=samesite,
            secure=cookie_secure,
        )
        if js not in seen:
            seen.add(js)
            attempts.append(js)

    add(cookie_path=path, cookie_domain=domain, cookie_secure=secure)
    add(cookie_path=path, cookie_domain=domain, cookie_secure=False)
    add(cookie_path="/", cookie_domain=domain, cookie_secure=secure)
    add(cookie_path="/", cookie_domain=domain, cookie_secure=False)
    add(cookie_path=path, cookie_domain=None, cookie_secure=secure)
    add(cookie_path=path, cookie_domain=None, cookie_secure=False)
    add(cookie_path="/", cookie_domain=None, cookie_secure=secure)
    add(cookie_path="/", cookie_domain=None, cookie_secure=False)
    if domain:
        dotted = domain if domain.startswith(".") else f".{domain.lstrip('.')}"
        if dotted != domain:
            add(cookie_path=path, cookie_domain=dotted, cookie_secure=secure)
            add(cookie_path="/", cookie_domain=dotted, cookie_secure=False)
    return " ".join(attempts)


def _document_auth_cookies_scan_clear_js() -> str:
    """Scan ``document.cookie`` and expire every visible auth cookie name."""
    names = json.dumps(sorted(auth_cookie_names()))
    return (
        "(function(){"
        f"var names={names};"
        "var expire='; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';"
        "try{"
        "(document.cookie||'').split(';').forEach(function(raw){"
        "var eq=raw.indexOf('=');"
        "var n=(eq<0?raw:raw.slice(0,eq)).trim();"
        "if(names.indexOf(n)<0)return;"
        "document.cookie=n+'='+expire+'; path=/';"
        "document.cookie=n+'='+expire+'; path=/; samesite=Lax';"
        "document.cookie=n+'='+expire+'; path=/; secure; samesite=Lax';"
        "document.cookie=n+'='+expire+'; path=/; secure';"
        "});"
        "}catch(e){}"
        "})();"
    )


def _cookie_attrs_from_settings(prefix: str) -> tuple[str, str]:
    """Return ``(cookie_name, attribute_suffix)`` for ``document.cookie`` writes."""
    from django.conf import settings as django_settings

    name = getattr(
        django_settings,
        f"{prefix}_COOKIE_NAME",
        "sessionid" if prefix == "SESSION" else "csrftoken",
    )
    path = getattr(django_settings, f"{prefix}_COOKIE_PATH", "/") or "/"
    samesite = getattr(django_settings, f"{prefix}_COOKIE_SAMESITE", "Lax") or "Lax"
    secure = bool(getattr(django_settings, f"{prefix}_COOKIE_SECURE", False))
    domain = getattr(django_settings, f"{prefix}_COOKIE_DOMAIN", None)
    domain_part = f"; domain={domain}" if domain else ""
    secure_part = "; secure" if secure else ""
    if prefix == "SESSION":
        max_age = int(getattr(django_settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 14))
        return name, (
            f"path={path}; max-age={max_age}; samesite={samesite}"
            f"{secure_part}{domain_part}"
        )
    return name, f"path={path}; samesite={samesite}{secure_part}{domain_part}"


def session_cookie_name_and_suffix() -> tuple[str, str]:
    """Return ``(cookie_name, attribute_suffix)`` for session ``document.cookie`` writes.

    Returns:
        Tuple of cookie name and formatted attribute suffix.
    """
    return _cookie_attrs_from_settings("SESSION")


def csrf_cookie_name_and_suffix() -> tuple[str, str]:
    """Return ``(cookie_name, attribute_suffix)`` for CSRF ``document.cookie`` writes."""
    return _cookie_attrs_from_settings("CSRF")


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

    Uses several path/domain/secure combinations plus a ``document.cookie`` scan
    so stale ``sessionid`` values are removed even when attribute sets differ.

    Returns:
        JS suitable for ``rx.call_script``.
    """
    name, _ = session_cookie_name_and_suffix()
    from django.conf import settings as django_settings

    path = getattr(django_settings, "SESSION_COOKIE_PATH", "/") or "/"
    domain = getattr(django_settings, "SESSION_COOKIE_DOMAIN", None)
    samesite = getattr(django_settings, "SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
    secure = bool(getattr(django_settings, "SESSION_COOKIE_SECURE", False))
    return " ".join(
        (
            _cookie_clear_variants_js(
                name,
                path=path,
                domain=domain,
                samesite=samesite,
                secure=secure,
            ),
            _document_auth_cookies_scan_clear_js(),
        )
    )


def csrf_cookie_clear_js() -> str:
    """JavaScript snippet that expires the CSRF cookie in the browser."""
    name, _ = csrf_cookie_name_and_suffix()
    from django.conf import settings as django_settings

    path = getattr(django_settings, "CSRF_COOKIE_PATH", "/") or "/"
    domain = getattr(django_settings, "CSRF_COOKIE_DOMAIN", None)
    samesite = getattr(django_settings, "CSRF_COOKIE_SAMESITE", "Lax") or "Lax"
    secure = bool(getattr(django_settings, "CSRF_COOKIE_SECURE", False))
    return _cookie_clear_variants_js(
        name,
        path=path,
        domain=domain,
        samesite=samesite,
        secure=secure,
    )


def browser_auth_cookies_clear_js() -> str:
    """Expire session and CSRF cookies visible to ``document.cookie``."""
    return f"{session_cookie_clear_js()} {csrf_cookie_clear_js()}"


# Reflex WebSocket client id (see ``.web/utils/state.js`` ``TOKEN_KEY``).
_REFLEX_CLIENT_TOKEN_KEY = "token"


def browser_reflex_token_clear_js() -> str:
    """Remove Reflex's websocket client id from ``sessionStorage`` only."""
    key = _REFLEX_CLIENT_TOKEN_KEY.replace("\\", "\\\\").replace("'", "\\'")
    return (
        f"try{{if(typeof sessionStorage!=='undefined')"
        f"sessionStorage.removeItem('{key}');}}"
        "catch(e){}"
    )


def browser_session_storage_clear_js() -> str:
    """Clear Reflex websocket ``token`` in ``sessionStorage`` before auth navigation."""
    return browser_reflex_token_clear_js()


def browser_client_storage_clear_js() -> str:
    """Clear Reflex ``token`` and all ``localStorage`` for this origin.

    Prefer :func:`browser_auth_logout_clear_js` for logout; this helper remains
    for callers that intentionally wipe all client storage.
    """
    return (
        f"{browser_reflex_token_clear_js()} "
        "try{if(typeof localStorage!=='undefined')localStorage.clear();}"
        "catch(e){}"
    )


def browser_auth_logout_clear_js() -> str:
    """Expire auth cookies and drop Reflex websocket ``token`` before navigation.

    Reflex persists the websocket client id in ``sessionStorage`` under ``token``.
    After logout, a stale token can reconnect to server state that still looks
    authenticated while cookies are empty, causing a ``/`` ↔ ``/login`` loop until
    storage is cleared manually. Non-auth ``localStorage`` (theme, etc.) is preserved.
    """
    return f"{browser_auth_cookies_clear_js()} {browser_reflex_token_clear_js()}"


def auth_cookie_names() -> frozenset[str]:
    """Django session and CSRF cookie names from settings."""
    from django.conf import settings as django_settings

    return frozenset(
        {
            getattr(django_settings, "SESSION_COOKIE_NAME", "sessionid"),
            getattr(django_settings, "CSRF_COOKIE_NAME", "csrftoken"),
        }
    )


def strip_auth_cookies_from_cookie_header(cookie_header: str) -> str:
    """Remove session and CSRF cookies from a ``Cookie`` header string."""
    if not cookie_header:
        return ""
    names = auth_cookie_names()
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return cookie_header
    for name in list(jar.keys()):
        if name in names:
            del jar[name]
    if not jar:
        return ""
    return "; ".join(f"{key}={morsel.value}" for key, morsel in jar.items())


def strip_auth_cookies_from_router_data(router_data: dict[str, Any]) -> dict[str, Any]:
    """Return ``router_data`` without session/CSRF entries in ``headers.cookie``."""
    headers = dict(router_data.get("headers") or {})
    cookie_header = headers.get("cookie", "")
    if not cookie_header:
        return router_data
    stripped = strip_auth_cookies_from_cookie_header(cookie_header)
    if stripped == cookie_header:
        return router_data
    new_headers = {**headers, "cookie": stripped}
    return {**router_data, "headers": new_headers}


def merge_session_cookie_into_cookie_header(
    cookie_header: str,
    session_key: str,
) -> str:
    """Set ``sessionid`` on a ``Cookie`` header, preserving unrelated cookies.

    Strips any existing session/CSRF entries first (symmetric with logout).
    """
    if not session_key:
        return strip_auth_cookies_from_cookie_header(cookie_header)
    name, _ = session_cookie_name_and_suffix()
    base = strip_auth_cookies_from_cookie_header(cookie_header)
    session_pair = f"{name}={session_key}"
    if not base:
        return session_pair
    return f"{base}; {session_pair}"


def merge_session_cookie_into_router_data(
    router_data: dict[str, Any],
    session_key: str,
) -> dict[str, Any]:
    """Return ``router_data`` with ``sessionid`` merged into ``headers.cookie``."""
    if not session_key:
        return router_data
    headers = dict(router_data.get("headers") or {})
    cookie_header = headers.get("cookie", "")
    merged = merge_session_cookie_into_cookie_header(cookie_header, session_key)
    if merged == cookie_header:
        return router_data
    new_headers = {**headers, "cookie": merged}
    return {**router_data, "headers": new_headers}


def mirror_auth_cookies_to_state_tree(state: Any, session_key: str) -> None:
    """Mirror ``sessionid`` into ``router_data`` on every node in the state tree.

    Inverse of :func:`clear_auth_cookies_from_state_tree` after login so
    :func:`~reflex_django.bridge.event.router_data._resolve_router_data` can fall back to
    persisted cookies when events omit ``router_data`` headers.
    """
    if not session_key:
        return

    from reflex_django.bridge.state_tree import walk_substates_dfs

    def _mirror(node: Any) -> None:
        raw = getattr(node, "router_data", None)
        if isinstance(raw, dict):
            merged = merge_session_cookie_into_router_data(raw, session_key)
            if merged is not raw:
                node.router_data = merged

    walk_substates_dfs(state, _mirror)


def strip_auth_cookies_from_request(request: Any) -> None:
    """Remove session/CSRF cookies from a synthetic Django ``HttpRequest``."""
    names = auth_cookie_names()
    cookies = getattr(request, "COOKIES", None)
    if isinstance(cookies, dict):
        for name in names:
            cookies.pop(name, None)
    meta = getattr(request, "META", None)
    if isinstance(meta, dict) and meta.get("HTTP_COOKIE"):
        meta["HTTP_COOKIE"] = strip_auth_cookies_from_cookie_header(
            str(meta["HTTP_COOKIE"])
        )


def clear_auth_cookies_from_state_tree(state: Any) -> None:
    """Strip persisted session cookies from ``router_data`` on the Reflex state tree."""
    from reflex_django.bridge.state_tree import walk_substates_dfs

    def _clear(node: Any) -> None:
        raw = getattr(node, "router_data", None)
        if isinstance(raw, dict):
            stripped = strip_auth_cookies_from_router_data(raw)
            if stripped is not raw:
                node.router_data = stripped

    walk_substates_dfs(state, _clear)


__all__ = [
    "auth_cookie_names",
    "browser_auth_cookies_clear_js",
    "browser_auth_logout_clear_js",
    "browser_client_storage_clear_js",
    "browser_reflex_token_clear_js",
    "browser_session_storage_clear_js",
    "clear_auth_cookies_from_state_tree",
    "csrf_cookie_clear_js",
    "csrf_cookie_name_and_suffix",
    "merge_session_cookie_into_cookie_header",
    "merge_session_cookie_into_router_data",
    "mirror_auth_cookies_to_state_tree",
    "session_cookie_clear_js",
    "session_cookie_name_and_suffix",
    "session_cookie_set_js",
    "strip_auth_cookies_from_cookie_header",
    "strip_auth_cookies_from_request",
    "strip_auth_cookies_from_router_data",
]
