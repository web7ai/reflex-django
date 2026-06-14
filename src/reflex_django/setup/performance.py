"""Performance preset helpers for Django settings."""

from __future__ import annotations

_LEAN_OVERRIDES = {
    "REFLEX_DJANGO_AUTH_AUTO_SYNC": False,
    "REFLEX_DJANGO_MIRROR_MESSAGES": False,
    "REFLEX_DJANGO_MIRROR_CSRF": False,
    "REFLEX_DJANGO_MIRROR_LANGUAGE": False,
}


def apply_performance_preset() -> None:
    """Apply lean defaults when preset is enabled."""
    try:
        from django.conf import settings
    except Exception:
        return

    preset = str(getattr(settings, "REFLEX_DJANGO_PERFORMANCE_PRESET", "default")).strip().lower()
    if preset != "lean":
        return

    try:
        from reflex_django.setup import default_settings as defaults
    except Exception:
        return

    for key, lean_value in _LEAN_OVERRIDES.items():
        if not hasattr(settings, key):
            continue
        if getattr(settings, key) == getattr(defaults, key, None):
            setattr(settings, key, lean_value)


__all__ = ["apply_performance_preset"]