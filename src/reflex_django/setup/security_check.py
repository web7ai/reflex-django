"""Loud warnings for insecure Django configuration in production.

reflex-django ships permissive defaults so ``reflex run`` works out of the box
(random per-process ``SECRET_KEY``, ``DEBUG=True``, ``ALLOWED_HOSTS=['*']``,
and ``SESSION_COOKIE_HTTPONLY=False`` for the WebSocket cookie-sync login).
Those are fine for development but dangerous in production. This module audits
the active settings and emits a single, loud warning when it detects a
production posture with insecure values.
"""

from __future__ import annotations

import os

# Emit the audit at most once per process unless ``force=True``.
_WARNED = False


def collect_insecure_default_warnings() -> list[str]:
    """Return human-readable warnings for insecure settings (empty if clean)."""
    try:
        from django.conf import settings
    except Exception:
        return []

    issues: list[str] = []
    auto = bool(getattr(settings, "RX_AUTO_SETTINGS", False))

    if auto:
        issues.append(
            "Using reflex-django's auto-generated default settings module. Set "
            "DJANGO_SETTINGS_MODULE to your own settings for production."
        )
    if auto and not os.environ.get("RX_SECRET_KEY"):
        issues.append(
            "SECRET_KEY is randomly generated per process. Sessions and signed "
            "values break on restart and differ across workers — set RX_SECRET_KEY "
            "or a real settings module."
        )
    if getattr(settings, "DEBUG", False):
        issues.append("DEBUG is True. Set DEBUG=False (RX_DEBUG=0) in production.")
    hosts = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
    if "*" in hosts:
        issues.append(
            "ALLOWED_HOSTS contains '*'. Restrict it to your domain(s) in production."
        )
    if getattr(settings, "SESSION_COOKIE_HTTPONLY", True) is False:
        issues.append(
            "SESSION_COOKIE_HTTPONLY is False (enables reflex-django cookie-sync "
            "login). The session cookie is readable by JavaScript — serve over "
            "HTTPS, keep SESSION_COOKIE_SAMESITE='Lax' or 'Strict', and review the "
            "trade-off in docs/advanced/security.md."
        )
    if not getattr(settings, "SESSION_COOKIE_SECURE", False):
        issues.append("SESSION_COOKIE_SECURE is False. Set it True behind HTTPS.")
    if not getattr(settings, "CSRF_COOKIE_SECURE", False):
        issues.append("CSRF_COOKIE_SECURE is False. Set it True behind HTTPS.")
    return issues


def _is_production_posture(env_name: str | None) -> bool:
    """Whether we should treat the current run as production."""
    if env_name == "prod":
        return True
    try:
        from django.conf import settings

        return not bool(getattr(settings, "DEBUG", False))
    except Exception:
        return False


def warn_insecure_defaults(*, env_name: str | None = None, force: bool = False) -> bool:
    """Emit a loud warning when production runs with insecure defaults.

    Args:
        env_name: The Reflex env (``"prod"``/``"dev"``) when known. Falls back
            to ``not settings.DEBUG`` to decide whether this is production.
        force: Re-emit even if already warned this process.

    Returns:
        Whether a warning was emitted.
    """
    global _WARNED
    if _WARNED and not force:
        return False
    try:
        from django.conf import settings

        if not settings.configured:
            return False
    except Exception:
        return False

    if not _is_production_posture(env_name):
        return False

    issues = collect_insecure_default_warnings()
    _WARNED = True
    if not issues:
        return False

    from reflex_base.utils import console

    console.warn("reflex-django: insecure configuration detected for a production run:")
    for issue in issues:
        console.warn(f"  - {issue}")
    console.warn(
        "  See docs/advanced/security.md for hardening guidance (SECRET_KEY, "
        "HTTPS cookies, ALLOWED_HOSTS, and the .pth bootstrap)."
    )
    return True


def _reset_warned_for_tests() -> None:
    """Reset the one-shot guard (test helper)."""
    global _WARNED
    _WARNED = False


__all__ = [
    "collect_insecure_default_warnings",
    "warn_insecure_defaults",
]
