"""Discover Django-owned URL prefixes from ``urlpatterns``."""

from __future__ import annotations

import inspect
import re
import sys
from collections.abc import Sequence
from typing import Any

from reflex_django.prefixes import _normalize_path_prefix


def _first_segment(route: str) -> str | None:
    stripped = route.strip("/")
    if not stripped:
        return None
    return stripped.split("/")[0]


def _is_reflex_mount_pattern(pattern: Any) -> bool:
    from reflex_django.views.mount import ReflexMountView

    callback = getattr(pattern, "callback", None)
    if callback is None:
        return False
    view_class = getattr(callback, "view_class", None)
    if view_class is ReflexMountView:
        return True
    cls = getattr(callback, "cls", None)
    return cls is ReflexMountView


def _route_from_regex_pattern(raw: str) -> str | None:
    """Extract a path-like prefix from a Django ``RoutePattern`` regex string."""
    if raw in (r"\Z", r"^\Z"):
        return ""
    body = raw[1:] if raw.startswith("^") else raw
    match = re.match(r"^([^($<\\]+)", body)
    if not match:
        return None
    literal = match.group(1).rstrip("/")
    if not literal:
        return ""
    return f"{literal}/"


def _route_string(pattern: Any) -> str | None:
    route_pattern = getattr(pattern, "pattern", None)
    if route_pattern is None:
        return None
    route = getattr(route_pattern, "route", None)
    if isinstance(route, str):
        return route
    compiled = getattr(route_pattern, "regex", None)
    if compiled is not None:
        raw = getattr(compiled, "pattern", None)
        if isinstance(raw, str):
            return _route_from_regex_pattern(raw)
    return None


def _media_url_prefix() -> str | None:
    try:
        from django.conf import settings
    except Exception:
        return None
    if not getattr(settings, "DEBUG", False):
        return None
    media_url = getattr(settings, "MEDIA_URL", None)
    if not isinstance(media_url, str) or not media_url or "://" in media_url:
        return None
    normalized = _normalize_path_prefix(media_url)
    if not normalized or normalized == "/":
        return None
    return normalized


def discover_django_prefixes(urlpatterns: Sequence[Any]) -> tuple[str, ...]:
    """Return first-segment prefixes for top-level ``path()`` entries.

    Walks only the patterns passed in (no nested ``include()`` descent). Skips
    empty routes, :class:`~reflex_django.views.mount.ReflexMountView` patterns,
    and deduplicates. When ``DEBUG`` is on and ``MEDIA_URL`` is a local path,
    ``/media`` (or the configured prefix) is included even if not in the list.
    """
    seen: dict[str, None] = {}
    for pattern in urlpatterns:
        if _is_reflex_mount_pattern(pattern):
            continue
        route = _route_string(pattern)
        if route is None:
            continue
        segment = _first_segment(route)
        if not segment:
            continue
        prefix = _normalize_path_prefix(f"/{segment}")
        if prefix:
            seen[prefix] = None
    media = _media_url_prefix()
    if media:
        seen[media] = None
    return tuple(sorted(seen.keys()))


def caller_urlpatterns() -> list[Any] | None:
    """Return ``urlpatterns`` from the direct caller (module-level ``+=``)."""
    frame = inspect.currentframe()
    if frame is None:
        return None
    caller = frame.f_back
    if caller is None:
        return None
    patterns = caller.f_locals.get("urlpatterns")
    if not isinstance(patterns, list):
        patterns = caller.f_globals.get("urlpatterns")
    if isinstance(patterns, list):
        return patterns
    mod_name = caller.f_globals.get("__name__")
    if isinstance(mod_name, str):
        mod = sys.modules.get(mod_name)
        if mod is not None:
            mod_patterns = getattr(mod, "urlpatterns", None)
            if isinstance(mod_patterns, list):
                return mod_patterns
    return _root_urlconf_urlpatterns()


def _root_urlconf_urlpatterns() -> list[Any] | None:
    """Return ``urlpatterns`` from the loaded ``ROOT_URLCONF`` module."""
    try:
        from django.conf import settings
    except Exception:
        return None
    urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not isinstance(urlconf, str) or not urlconf:
        return None
    mod = sys.modules.get(urlconf)
    if mod is None:
        return None
    patterns = getattr(mod, "urlpatterns", None)
    if isinstance(patterns, list):
        return patterns
    return None


def resolve_django_prefix(
    django_prefix: str | tuple[str, ...] | None,
    *,
    urlpatterns: Sequence[Any] | None = None,
) -> tuple[str, ...]:
    """Resolve ``django_prefix`` for :func:`reflex_django.urls.reflex_mount`.

    ``None`` auto-discovers from ``urlpatterns`` (explicit arg or caller frame).
    ``()`` means no Django prefixes. A non-empty str/tuple is used as-is.
    """
    if django_prefix is not None:
        if isinstance(django_prefix, str):
            return (django_prefix,) if django_prefix.strip() else ()
        return tuple(str(p) for p in django_prefix if str(p).strip())
    patterns = list(urlpatterns) if urlpatterns is not None else caller_urlpatterns()
    if not patterns:
        return ()
    return discover_django_prefixes(patterns)


__all__ = [
    "caller_urlpatterns",
    "discover_django_prefixes",
    "resolve_django_prefix",
]
