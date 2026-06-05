"""Reflex ``app`` entry for Django-first projects (no ``{app}/{app}.py`` on disk)."""

from __future__ import annotations

from typing import Any

_app: Any | None = None


def __getattr__(name: str) -> Any:
    if name == "app":
        return _load_app()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def _load_app() -> Any:
    global _app
    if _app is None:
        from reflex_django.app_factory import get_or_create_app

        _app = get_or_create_app()
    return _app
