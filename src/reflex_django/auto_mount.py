"""Settings-driven SPA mount and :func:`reflex_django.urls.reflex_mount` helpers."""

from __future__ import annotations

import logging
import os
import warnings
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from django.urls import URLPattern

logger = logging.getLogger("reflex_django.auto_mount")

_MOUNT_BOOT_COMPLETED = False
_MOUNT_HANDLE: ReflexMountHandle | None = None
_SETTINGS_MOUNT_REGISTERED = False


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
    env = os.environ.get("REFLEX_DJANGO_AUTO_MOUNT")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    try:
        from django.conf import settings

        return bool(getattr(settings, "REFLEX_DJANGO_AUTO_MOUNT", True))
    except Exception:
        return True


def _should_auto_mount_urls() -> bool:
    from reflex_django.routing import UrlRoutingMode, resolve_url_routing

    return resolve_url_routing() == UrlRoutingMode.DJANGO_OUTER


def has_reflex_mount(urlpatterns: Sequence[Any]) -> bool:
    """Return whether *urlpatterns* already contains a :class:`~reflex_django.views.mount.ReflexMountView` pattern."""
    from reflex_django.prefix_discovery import _is_reflex_mount_pattern

    return any(_is_reflex_mount_pattern(p) for p in urlpatterns)


def register_mount_from_settings(**overrides: Any) -> None:
    """Register rx config from settings + *overrides* (idempotent, no URL append)."""
    global _SETTINGS_MOUNT_REGISTERED
    from reflex_django.mount_config import has_mount_rx_config, register_mount_rx_config
    from reflex_django.rxconfig_bridge import _coerce_rx_config_dict

    if has_mount_rx_config() and _SETTINGS_MOUNT_REGISTERED:
        return

    try:
        from django.conf import settings as django_settings

        settings_rx = getattr(django_settings, "REFLEX_DJANGO_RX_CONFIG", None) or {}
        mount_prefix = getattr(
            django_settings,
            "REFLEX_DJANGO_MOUNT_PREFIX",
            os.environ.get("REFLEX_DJANGO_MOUNT_PREFIX", "/"),
        )
        settings_django_prefix = getattr(
            django_settings,
            "REFLEX_DJANGO_DJANGO_PREFIX",
            None,
        )
    except Exception:
        settings_rx = {}
        mount_prefix = os.environ.get("REFLEX_DJANGO_MOUNT_PREFIX", "/")
        settings_django_prefix = None

    opts = dict(overrides)
    merged_rx = _coerce_rx_config_dict(
        {**dict(settings_rx), **dict(opts.get("rx_config") or {})}
    )
    app_name_override = opts.get("app_name")
    if app_name_override:
        merged_rx["app_name"] = app_name_override

    register_mount_rx_config(
        app_name=app_name_override or merged_rx.get("app_name"),
        plugins=opts.get("plugins"),
        rx_config=merged_rx,
        django_plugin=opts.get("django_plugin"),
        mount_prefix=opts.get("mount_prefix", mount_prefix),
        django_prefix=opts.get("django_prefix", settings_django_prefix),
    )
    _SETTINGS_MOUNT_REGISTERED = True


def ensure_reflex_mount(
    *,
    app_name: str | None = None,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
    urlpatterns: Sequence[Any] | None = None,
    plugins: Sequence[Any] | None = None,
    rx_config: Mapping[str, Any] | None = None,
    django_plugin: Mapping[str, Any] | None = None,
    append_to_urlconf: bool = False,
) -> ReflexMountHandle:
    """Register mount config and return the catch-all URL handle."""
    global _MOUNT_HANDLE

    if app_name is not None:
        warnings.warn(
            "reflex_mount(app_name=...) is deprecated; set app_name in "
            "REFLEX_DJANGO_RX_CONFIG in Django settings instead.",
            DeprecationWarning,
            stacklevel=3,
        )

    from reflex_django.mount_config import register_mount_rx_config
    from reflex_django.prefix_discovery import resolve_django_prefix
    from reflex_django.prefixes import export_prefix_env, export_rx_port_env, resolve_prefixes
    from reflex_django.rxconfig_bridge import _coerce_rx_config_dict
    from reflex_django.urls import _reflex_catchall_pattern  # lazy: urls imports auto_mount in reflex_mount only

    if mount_prefix is None:
        try:
            from django.conf import settings as django_settings

            mount_prefix = str(
                getattr(
                    django_settings,
                    "REFLEX_DJANGO_MOUNT_PREFIX",
                    os.environ.get("REFLEX_DJANGO_MOUNT_PREFIX", "/"),
                )
            )
        except Exception:
            mount_prefix = os.environ.get("REFLEX_DJANGO_MOUNT_PREFIX", "/")

    resolved_django_prefix = resolve_django_prefix(
        django_prefix,
        urlpatterns=urlpatterns,
    )

    try:
        from django.conf import settings as django_settings

        settings_rx = getattr(django_settings, "REFLEX_DJANGO_RX_CONFIG", None) or {}
    except Exception:
        settings_rx = {}

    merged_rx = _coerce_rx_config_dict({**dict(settings_rx), **dict(rx_config or {})})
    if app_name:
        merged_rx["app_name"] = app_name

    register_mount_rx_config(
        app_name=app_name or merged_rx.get("app_name"),
        plugins=plugins,
        rx_config=merged_rx,
        django_plugin=django_plugin,
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
        logger.warning("reflex-django: REFLEX_DJANGO_AUTO_MOUNT skipped — ROOT_URLCONF unset.")
        return

    from importlib import import_module

    mod = import_module(urlconf_name)
    patterns = list(urlpatterns) if urlpatterns is not None else list(getattr(mod, "urlpatterns", []) or [])
    if has_reflex_mount(patterns):
        return
    mod_urlpatterns = getattr(mod, "urlpatterns", None)
    if not isinstance(mod_urlpatterns, list):
        logger.warning(
            "reflex-django: REFLEX_DJANGO_AUTO_MOUNT skipped — %s.urlpatterns is not a list.",
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
    """Rebuild the SPA catch-all after runtime env overrides (e.g. ``run_reflex``).

    ``AppConfig.ready()`` mounts the catch-all while Django boots, which is
    before ``manage.py run_reflex`` sets ``REFLEX_DJANGO_SEPARATE_DEV_PORTS``.
    Projects that set ``REFLEX_DJANGO_SEPARATE_DEV_PORTS = True`` in dev
    settings would otherwise keep ``/`` reserved even in ``--env prod`` mode.
    """
    global _MOUNT_HANDLE

    from django.urls import clear_url_caches

    from reflex_django.prefix_discovery import _is_reflex_mount_pattern

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
    """Return whether ``reflex_django`` is listed before ``django.contrib.admin``."""
    try:
        from django.conf import settings

        installed = list(getattr(settings, "INSTALLED_APPS", ()))
        return installed.index("reflex_django") < installed.index("django.contrib.admin")
    except ValueError:
        return False


def schedule_auto_mount_after_admin() -> None:
    """Schedule :func:`maybe_auto_mount` once admin autodiscover has finished.

    ``ReflexDjangoConfig.ready()`` can run before ``django.contrib.admin``
    autodiscover. Importing ``ROOT_URLCONF`` at that point evaluates
    ``admin.site.urls`` while the admin registry is still empty, so Django
    never registers the per-app ``app_list`` routes and ``/admin/`` raises
    ``NoReverseMatch`` for ``admin:app_list``.
    """
    from django.contrib.admin.apps import AdminConfig

    if getattr(AdminConfig, "_reflex_auto_mount_scheduled", False):
        return
    AdminConfig._reflex_auto_mount_scheduled = True

    if not _auto_mount_enabled() or not _should_auto_mount_urls():
        return

    if not _reflex_before_admin_in_installed_apps():
        maybe_auto_mount()
        return

    original_ready = AdminConfig.ready

    def ready_with_auto_mount(self: AdminConfig, *args: Any, **kwargs: Any) -> None:
        original_ready(self, *args, **kwargs)
        maybe_auto_mount()

    AdminConfig.ready = ready_with_auto_mount  # type: ignore[method-assign]


def maybe_auto_mount() -> ReflexMountHandle | None:
    """Append SPA catch-all from settings when enabled (boot-only, idempotent)."""
    global _MOUNT_BOOT_COMPLETED, _MOUNT_HANDLE

    if _MOUNT_BOOT_COMPLETED:
        return _MOUNT_HANDLE

    if not _auto_mount_enabled() or not _should_auto_mount_urls():
        _MOUNT_BOOT_COMPLETED = True
        return _MOUNT_HANDLE

    register_mount_from_settings()

    try:
        from django.conf import settings
    except Exception:
        _MOUNT_BOOT_COMPLETED = True
        return _MOUNT_HANDLE

    urlconf_name = getattr(settings, "ROOT_URLCONF", None)
    patterns: list[Any] = []
    if isinstance(urlconf_name, str) and urlconf_name:
        from importlib import import_module

        mod = import_module(urlconf_name)
        raw = getattr(mod, "urlpatterns", None)
        if isinstance(raw, list):
            patterns = list(raw)

    if has_reflex_mount(patterns):
        _MOUNT_BOOT_COMPLETED = True
        if _MOUNT_HANDLE is None and patterns:
            from reflex_django.prefix_discovery import _is_reflex_mount_pattern

            for p in patterns:
                if _is_reflex_mount_pattern(p):
                    _MOUNT_HANDLE = ReflexMountHandle(p)
                    break
        return _MOUNT_HANDLE

    handle = ensure_reflex_mount(urlpatterns=patterns, append_to_urlconf=True)
    _MOUNT_BOOT_COMPLETED = True
    return handle


def clear_auto_mount_state() -> None:
    """Reset auto-mount module state (tests only)."""
    global _MOUNT_BOOT_COMPLETED, _MOUNT_HANDLE, _SETTINGS_MOUNT_REGISTERED
    _MOUNT_BOOT_COMPLETED = False
    _MOUNT_HANDLE = None
    _SETTINGS_MOUNT_REGISTERED = False
    try:
        from django.contrib.admin.apps import AdminConfig

        if hasattr(AdminConfig, "_reflex_auto_mount_scheduled"):
            delattr(AdminConfig, "_reflex_auto_mount_scheduled")
    except Exception:
        pass


__all__ = [
    "ReflexMountHandle",
    "clear_auto_mount_state",
    "ensure_reflex_mount",
    "has_reflex_mount",
    "maybe_auto_mount",
    "refresh_reflex_mount_catchall",
    "register_mount_from_settings",
    "schedule_auto_mount_after_admin",
]
