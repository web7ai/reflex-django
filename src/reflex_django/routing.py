"""URL routing modes for reflex-django's ASGI composition.

Two modes are supported:

- :attr:`UrlRoutingMode.DJANGO_OUTER` — Django is the outer ASGI app on a
  single port (default). Reflex Socket.IO, upload, and health endpoints are
  mounted under Django via
  :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`.
- :attr:`UrlRoutingMode.REFLEX_OUTER` — Reflex is the outer ASGI app on a
  single public port. Django admin/API/static HTTP runs in a separate worker
  proxied by Reflex. See docs/routing.md.
"""

from __future__ import annotations

import enum
import os

from reflex_django.errors import RoutingModeError

_LEGACY_MODES = frozenset({
    "reflex",
    "reflex_led",
    "reflexled",
    "django_led",
    "djangoled",
})


class UrlRoutingMode(enum.Enum):
    """How HTTP paths and lifespan are split between Django and Reflex."""

    REFLEX_OUTER = "reflex_outer"
    DJANGO_OUTER = "django_outer"


_DEFAULT_MODE = UrlRoutingMode.DJANGO_OUTER

_ALIASES = {
    "reflex_outer": UrlRoutingMode.REFLEX_OUTER,
    "reflexouter": UrlRoutingMode.REFLEX_OUTER,
    "django": UrlRoutingMode.DJANGO_OUTER,
    "django_outer": UrlRoutingMode.DJANGO_OUTER,
    "djangoouter": UrlRoutingMode.DJANGO_OUTER,
    "outer": UrlRoutingMode.DJANGO_OUTER,
}


def _raise_if_legacy(raw: str) -> None:
    key = raw.strip().lower()
    if key in _LEGACY_MODES:
        raise RoutingModeError(
            f"Routing mode {raw!r} was removed in reflex-django 1.0. "
            "Use 'django_outer' (default) or 'reflex_outer'. "
            "See docs/migration/v0-to-v1.md."
        )


def _coerce(raw: str) -> UrlRoutingMode | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if not key or key in {"auto", "default"}:
        return None
    _raise_if_legacy(raw)
    mode = _ALIASES.get(key)
    if mode is None:
        raise RoutingModeError(
            f"Unknown routing mode {raw!r}. "
            "Supported values: django_outer, reflex_outer."
        )
    return mode


def resolve_url_routing() -> UrlRoutingMode:
    """Resolve URL routing mode from env or Django settings."""
    env_raw = os.environ.get("REFLEX_DJANGO_URL_ROUTING", "")
    if env_raw:
        env_mode = _coerce(env_raw)
        if env_mode is not None:
            return env_mode

    try:
        from django.conf import settings

        if settings.configured:
            settings_raw = str(getattr(settings, "REFLEX_DJANGO_URL_ROUTING", ""))
            if settings_raw:
                settings_mode = _coerce(settings_raw)
                if settings_mode is not None:
                    return settings_mode
    except RoutingModeError:
        raise
    except Exception:
        pass

    return _DEFAULT_MODE


__all__ = ["UrlRoutingMode", "resolve_url_routing"]
