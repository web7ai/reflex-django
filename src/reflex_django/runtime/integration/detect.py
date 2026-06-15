"""Detect ReflexDjangoPlugin in an on-disk `rx.Config`."""

from __future__ import annotations

from typing import Any


def detect_reflex_django_plugin(config: Any) -> Any | None:
    """Return the :class:~reflex_django.plugins.ReflexDjangoPlugin from *config*, if any."""
    from reflex_django.plugins.reflex_django import is_reflex_django_plugin

    for plugin in getattr(config, "plugins", None) or ():
        if is_reflex_django_plugin(plugin):
            return plugin
    return None
