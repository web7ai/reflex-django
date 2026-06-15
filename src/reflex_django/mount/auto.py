"""SPA mount and :func:`reflex_django.django.urls.reflex_mount` helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Sequence
from typing import Any

from django.urls import URLPattern

logger = logging.getLogger("reflex_django.mount.auto")

_MOUNT_BOOT_COMPLETED = False
_MOUNT_HANDLE: ReflexMountHandle | None = None
_ADMIN_AUTODISCOVER_COMPLETE = False


class ReflexMountHandle:
    """URL-only result of :func:`ensure_reflex_mount` — iterable catch-all pattern."""

    def __init__(self, url_pattern: URLPattern) -> None:
        self._url_pattern = url_pattern

    @property
    def urlpatterns(self) -> list[URLPattern]:
        return [self._url_pattern]

    @property
    def url_pattern(self) -> URLPattern:
        return self._url_pattern

    def __iter__(self) -> Iterator[URLPattern]:
        return iter(self.urlpatterns)

    @property
    def pattern(self) -> Any:
        return self._url_pattern.pattern

    @property
    def name(self) -> str | None:
        return self._url_pattern.name

    @property
    def callback(self) -> Any:
        return self._url_pattern.callback


def _auto_mount_enabled() -> bool:
    env = os.environ.get("RX_AUTO_MOUNT")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    return True


def has_reflex_mount(urlpatterns: Sequence[Any]) -> bool:
    from reflex_django.mount.discovery import _is_reflex_mount_pattern

    return any(_is_reflex_mount_pattern(p) for p in urlpatterns)


def ensure_reflex_mount(
    *,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
    urlpatterns: Sequence[Any] | None = None,
    append_to_urlconf: bool = False,
) -> ReflexMountHandle:
    """Register mount prefixes and return the catch-all URL handle."""
    global _MOUNT_HANDLE

    from reflex_django.mount.config import register_mount
    from reflex_django.mount.discovery import resolve_django_prefix
    from reflex_django.mount.prefixes import export_prefix_env, export_rx_port_env, resolve_prefixes
    from reflex_django.django.urls import _reflex_catchall_pattern

    if mount_prefix is None:
        mount_prefix = os.environ.get("RX_MOUNT_PREFIX", "/")

    resolved_django_prefix = resolve_django_prefix(
        django_prefix,
        urlpatterns=urlpatterns,
    )

    register_mount(
        mount_prefix=mount_prefix,
        django_prefix=resolved_django_prefix,
    )

    config = resolve_prefixes(
        mount_prefix=mount_prefix,
        django_prefix=resolved_django_prefix,
    )
    export_prefix_env(config)
    export_rx_port_env()

    pattern = _reflex_catchall_pattern(
        config.mount_prefix,
        config.reserved_paths_for_catchall(),
    )
    handle = ReflexMountHandle(pattern)

    if append_to_urlconf:
        _append_mount_to_root_urlconf(handle, urlpatterns=urlpatterns)

    if _MOUNT_HANDLE is None:
        _MOUNT_HANDLE = handle
    return handle


def _append_mount_to_root_urlconf(
    handle: ReflexMountHandle,
    *,
    urlpatterns: Sequence[Any] | None = None,
) -> None:
    from django.urls import clear_url_caches

    try:
        from django.conf import settings
    except Exception:
        return

    urlconf_name = getattr(settings, "ROOT_URLCONF", None)
    if not isinstance(urlconf_name, str) or not urlconf_name:
        logger.warning("reflex-django: auto_mount skipped — ROOT_URLCONF unset.")
        return

    from importlib import import_module

    mod = import_module(urlconf_name)
    patterns = list(urlpatterns) if urlpatterns is not None else list(getattr(mod, "urlpatterns", []) or [])
    if has_reflex_mount(patterns):
        return
    mod_urlpatterns = getattr(mod, "urlpatterns", None)
    if not isinstance(mod_urlpatterns, list):
        logger.warning(
            "reflex-django: auto_mount skipped — %s.urlpatterns is not a list.",
            urlconf_name,
        )
        return
    mod_urlpatterns.extend(handle.urlpatterns)
    clear_url_caches()
    logger.info(
        "reflex-django: auto-mounted Reflex SPA catch-all on %s (mount_prefix=%s).",
        urlconf_name,
        handle.url_pattern.pattern,
    )


def refresh_reflex_mount_catchall() -> ReflexMountHandle | None:
    global _MOUNT_HANDLE

    from django.urls import clear_url_caches

    from reflex_django.mount.discovery import _is_reflex_mount_pattern

    try:
        from django.conf import settings
    except Exception:
        return None

    urlconf_name = getattr(settings, "ROOT_URLCONF", None)
    if not isinstance(urlconf_name, str) or not urlconf_name:
        return None

    from importlib import import_module

    mod = import_module(urlconf_name)
    mod_urlpatterns = getattr(mod, "urlpatterns", None)
    if not isinstance(mod_urlpatterns, list):
        return None

    handle = ensure_reflex_mount(append_to_urlconf=False)
    if has_reflex_mount(mod_urlpatterns):
        for index, pattern in enumerate(mod_urlpatterns):
            if _is_reflex_mount_pattern(pattern):
                mod_urlpatterns[index] = handle.url_pattern
                break
    else:
        mod_urlpatterns.extend(handle.urlpatterns)

    _MOUNT_HANDLE = handle
    clear_url_caches()
    return handle


def _reflex_before_admin_in_installed_apps() -> bool:
    try:
        from django.conf import settings

        installed = list(getattr(settings, "INSTALLED_APPS", ()))
        return installed.index("reflex_django") < installed.index("django.contrib.admin")
    except ValueError:
        return False


def admin_autodiscover_complete() -> bool:
    return _ADMIN_AUTODISCOVER_COMPLETE


def mark_admin_autodiscover_complete() -> None:
    global _ADMIN_AUTODISCOVER_COMPLETE
    _ADMIN_AUTODISCOVER_COMPLETE = True


def should_defer_urlconf_import() -> bool:
    try:
        from django.conf import settings
    except Exception:
        return False
    if "django.contrib.admin" not in getattr(settings, "INSTALLED_APPS", ()):
        return False
    return _reflex_before_admin_in_installed_apps()


def refresh_urlconf_after_admin() -> None:
    from reflex_django.mount import config as mount_config
    from reflex_django.mount.config import (
        load_root_urlconf,
        urlconf_was_imported_before_admin,
    )

    mark_admin_autodiscover_complete()
    needs_reload = urlconf_was_imported_before_admin()
    if mount_config._URLCONF_IMPORT_DEFERRED or needs_reload:
        load_root_urlconf(reload_module=needs_reload)
        mount_config._URLCONF_IMPORT_DEFERRED = False
    elif not mount_config._URLCONF_IMPORTED:
        load_root_urlconf(reload_module=False)


def schedule_auto_mount_after_admin() -> None:
    from django.contrib.admin.apps import AdminConfig

    if getattr(AdminConfig, "_reflex_auto_mount_scheduled", False):
        return
    AdminConfig._reflex_auto_mount_scheduled = True

    if not _auto_mount_enabled():
        return

    if not _reflex_before_admin_in_installed_apps():
        maybe_auto_mount()
        return

    original_ready = AdminConfig.ready

    def ready_with_auto_mount(self: AdminConfig, *args: Any, **kwargs: Any) -> None:
        original_ready(self, *args, **kwargs)
        refresh_urlconf_after_admin()
        maybe_auto_mount()

    AdminConfig.ready = ready_with_auto_mount  # type: ignore[method-assign]


def _ensure_default_admin_urlpatterns(
    mod: Any,
    patterns: list[Any],
) -> list[Any]:
    try:
        from django.conf import settings
    except Exception:
        return patterns

    if "django.contrib.admin" not in getattr(settings, "INSTALLED_APPS", ()):
        return patterns

    from reflex_django.django.urls import admin_urlpatterns
    from reflex_django.mount.discovery import discover_django_prefixes

    if "/admin" in discover_django_prefixes(patterns):
        return patterns

    admin_patterns = admin_urlpatterns("/admin")
    if not admin_patterns:
        return patterns

    mod_urlpatterns = getattr(mod, "urlpatterns", None)
    if isinstance(mod_urlpatterns, list):
        mod_urlpatterns[:0] = admin_patterns
        from django.urls import clear_url_caches

        clear_url_caches()
        return list(mod_urlpatterns)

    return admin_patterns + patterns


def maybe_auto_mount() -> ReflexMountHandle | None:
    global _MOUNT_BOOT_COMPLETED, _MOUNT_HANDLE

    if _MOUNT_BOOT_COMPLETED:
        return _MOUNT_HANDLE

    if not _auto_mount_enabled():
        _MOUNT_BOOT_COMPLETED = True
        return _MOUNT_HANDLE

    try:
        from django.conf import settings
    except Exception:
        _MOUNT_BOOT_COMPLETED = True
        return _MOUNT_HANDLE

    urlconf_name = getattr(settings, "ROOT_URLCONF", None)
    patterns: list[Any] = []
    mod: Any | None = None
    if isinstance(urlconf_name, str) and urlconf_name:
        from importlib import import_module

        mod = import_module(urlconf_name)
        raw = getattr(mod, "urlpatterns", None)
        if isinstance(raw, list):
            patterns = list(raw)
        if mod is not None:
            patterns = _ensure_default_admin_urlpatterns(mod, patterns)

    if has_reflex_mount(patterns):
        _MOUNT_BOOT_COMPLETED = True
        if _MOUNT_HANDLE is None and patterns:
            from reflex_django.mount.discovery import _is_reflex_mount_pattern

            for p in patterns:
                if _is_reflex_mount_pattern(p):
                    _MOUNT_HANDLE = ReflexMountHandle(p)
                    break
        return _MOUNT_HANDLE

    handle = ensure_reflex_mount(urlpatterns=patterns, append_to_urlconf=True)
    _MOUNT_BOOT_COMPLETED = True
    return handle


def clear_auto_mount_state() -> None:
    global _MOUNT_BOOT_COMPLETED, _MOUNT_HANDLE, _ADMIN_AUTODISCOVER_COMPLETE
    _MOUNT_BOOT_COMPLETED = False
    _MOUNT_HANDLE = None
    _ADMIN_AUTODISCOVER_COMPLETE = False
    try:
        from django.contrib.admin.apps import AdminConfig

        if hasattr(AdminConfig, "_reflex_auto_mount_scheduled"):
            delattr(AdminConfig, "_reflex_auto_mount_scheduled")
    except Exception:
        pass


__all__ = [
    "ReflexMountHandle",
    "admin_autodiscover_complete",
    "clear_auto_mount_state",
    "ensure_reflex_mount",
    "has_reflex_mount",
    "maybe_auto_mount",
    "refresh_reflex_mount_catchall",
    "refresh_urlconf_after_admin",
    "schedule_auto_mount_after_admin",
    "should_defer_urlconf_import",
]
