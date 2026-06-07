"""Deprecated module path — use :mod:`reflex_django.reflex_app`."""

from __future__ import annotations

import warnings

from reflex_django.reflex_app import _app, _load_app

warnings.warn(
    "reflex_django.django_led_app is deprecated; use reflex_django.reflex_app.",
    DeprecationWarning,
    stacklevel=2,
)


def __getattr__(name: str):
    if name == "app":
        return _load_app()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = ["_app", "app"]
