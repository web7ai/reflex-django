"""Deprecated Reflex plugin stub (removed in v1.0)."""

from __future__ import annotations

from reflex_django.errors import DeprecationRemovedError

_REMOVED_MSG = (
    "ReflexDjangoPlugin was removed in reflex-django 1.0. "
    "Use Django-first setup: configure REFLEX_DJANGO_RX_CONFIG in settings.py, "
    "import views in urls.py, and run `python manage.py run_reflex`. "
    "See docs/migration/v0-to-v1.md."
)


class ReflexDjangoPlugin:
    """Removed plugin — raises :class:`DeprecationRemovedError` on construction."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise DeprecationRemovedError(_REMOVED_MSG)

    def __class_getitem__(cls, item: object) -> type:
        raise DeprecationRemovedError(_REMOVED_MSG)


def make_dispatcher(*args: object, **kwargs: object) -> None:
    """Removed legacy ASGI dispatcher helper."""
    raise DeprecationRemovedError(_REMOVED_MSG)


__all__ = ["ReflexDjangoPlugin", "make_dispatcher"]