"""URL routing modes for reflex-django's ASGI composition.

Three modes are supported:

- :attr:`UrlRoutingMode.REFLEX_LED` — Reflex is the outer ASGI app and
  Django is mounted as a sub-application by URL prefix. Use when your
  project is Reflex-first and Django is "embedded".
- :attr:`UrlRoutingMode.DJANGO_LED` — Reflex is still outer, but reserved
  Reflex paths are guaranteed to win the routing race. This was the
  default in early versions and remains a supported alias.
- :attr:`UrlRoutingMode.DJANGO_OUTER` — Django is the outer ASGI app on a
  single port (current default for new projects). Reflex's Socket.IO,
  upload, and health endpoints are mounted under Django via
  :class:`~reflex_django.django_outer_dispatcher.DjangoOuterDispatcher`,
  and the SPA bundle (or dev Vite reverse-proxy) is served by Django.
- :attr:`UrlRoutingMode.REFLEX_OUTER` — Reflex is the outer ASGI app on a
  single public port. Django admin/API/static HTTP runs in a separate worker
  and is reached via :mod:`reflex_django.django_http_proxy`; ORM and the
  event bridge stay in the Reflex process. See docs/routing.md.
"""

from __future__ import annotations

import enum
import os


class UrlRoutingMode(enum.Enum):
    """How HTTP paths and lifespan are split between Django and Reflex."""

    REFLEX_LED = "reflex_led"
    REFLEX_OUTER = "reflex_outer"
    DJANGO_LED = "django_led"
    DJANGO_OUTER = "django_outer"


_DEFAULT_MODE = UrlRoutingMode.DJANGO_OUTER


_ALIASES = {
    "reflex": UrlRoutingMode.REFLEX_LED,
    "reflex_led": UrlRoutingMode.REFLEX_LED,
    "reflexled": UrlRoutingMode.REFLEX_LED,
    "reflex_outer": UrlRoutingMode.REFLEX_OUTER,
    "reflexouter": UrlRoutingMode.REFLEX_OUTER,
    "django": UrlRoutingMode.DJANGO_OUTER,
    "django_led": UrlRoutingMode.DJANGO_LED,
    "djangoled": UrlRoutingMode.DJANGO_LED,
    "django_outer": UrlRoutingMode.DJANGO_OUTER,
    "djangoouter": UrlRoutingMode.DJANGO_OUTER,
    "outer": UrlRoutingMode.DJANGO_OUTER,
}


def _coerce(raw: str) -> UrlRoutingMode | None:
    if not raw:
        return None
    key = raw.strip().lower()
    if not key or key in {"auto", "default"}:
        return None
    return _ALIASES.get(key)


def resolve_url_routing() -> UrlRoutingMode:
    """Resolve URL routing mode.

    Resolution order:

    1. Environment variable ``REFLEX_DJANGO_URL_ROUTING``
       (``reflex_led`` | ``reflex_outer`` | ``django_led`` | ``django_outer`` | ``auto``).
    2. ``settings.REFLEX_DJANGO_URL_ROUTING`` when Django is configured.
    3. Default: :attr:`UrlRoutingMode.DJANGO_OUTER`.

    Returns:
        The active routing mode.
    """
    env_mode = _coerce(os.environ.get("REFLEX_DJANGO_URL_ROUTING", ""))
    if env_mode is not None:
        return env_mode

    try:
        from django.conf import settings

        if settings.configured:
            settings_mode = _coerce(
                str(getattr(settings, "REFLEX_DJANGO_URL_ROUTING", "")),
            )
            if settings_mode is not None:
                return settings_mode
    except Exception:
        pass

    return _DEFAULT_MODE


__all__ = ["UrlRoutingMode", "resolve_url_routing"]
