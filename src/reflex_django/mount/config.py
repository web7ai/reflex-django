"""Mount prefix registration from plugin config and ``reflex_mount()``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_URLCONF_IMPORTED = False
_URLCONF_IMPORT_DEFERRED = False
_URLCONF_IMPORTED_BEFORE_ADMIN = False


@dataclass(frozen=True)
class MountRegistration:
    """Path prefixes from plugin config or ``reflex_mount()``."""

    mount_prefix: str | None = None
    django_prefix: tuple[str, ...] | None = None
    app_name: str | None = None


_REGISTRATIONS: list[MountRegistration] = []


def default_app_name_from_project() -> str:
    """Derive a Reflex app name from the Django project directory (``manage.py`` parent)."""
    from reflex_django.setup.project import find_manage_py

    manage = find_manage_py()
    root = manage.parent if manage is not None else Path.cwd()
    name = root.name.replace("-", "_")
    if name == "reflex_django":
        return "web"
    return name


def _coerce_django_prefix(
    django_prefix: str | tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if django_prefix is None:
        return None
    if isinstance(django_prefix, str):
        return (django_prefix,) if django_prefix.strip() else ()
    return tuple(str(p) for p in django_prefix if str(p).strip())


def register_mount_from_plugin(plugin: Any) -> None:
    """Register mount config from a :class:`~reflex_django.plugins.ReflexDjangoPlugin`."""
    from reflex_django.plugins.reflex_django import is_reflex_django_plugin

    if not is_reflex_django_plugin(plugin):
        return

    cfg = getattr(plugin, "config", None) or {}
    register_mount(
        django_prefix=_coerce_django_prefix(cfg.get("django_prefix")),
        mount_prefix=cfg.get("mount_prefix"),
    )


def register_mount(
    *,
    app_name: str | None = None,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
) -> None:
    """Record mount prefixes from :func:`reflex_django.django.urls.reflex_mount`."""
    _REGISTRATIONS.append(
        MountRegistration(
            app_name=app_name,
            mount_prefix=mount_prefix,
            django_prefix=_coerce_django_prefix(django_prefix),
        )
    )


def get_merged_mount_registration() -> MountRegistration:
    """Merge all mount registrations (last non-None value wins per field)."""
    mount_prefix: str | None = None
    django_prefix: tuple[str, ...] | None = None
    app_name: str | None = None
    for registration in _REGISTRATIONS:
        if registration.mount_prefix is not None:
            mount_prefix = registration.mount_prefix
        if registration.django_prefix is not None:
            django_prefix = registration.django_prefix
        if registration.app_name is not None:
            app_name = registration.app_name
    return MountRegistration(
        app_name=app_name,
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
    )


def resolve_app_name() -> str:
    """Return Reflex ``app_name`` from ``rx.Config`` or mount registration."""
    try:
        from reflex_base.config import get_config

        config = get_config()
        if getattr(config, "app_name", None):
            return str(config.app_name).strip()
    except Exception:
        pass

    ensure_mount_config_loaded()
    mount = get_merged_mount_registration()
    if mount.app_name and str(mount.app_name).strip():
        return str(mount.app_name).strip()
    return default_app_name_from_project()


def has_mount_registration() -> bool:
    """Return whether mount prefixes have been registered."""
    return bool(_REGISTRATIONS)


def clear_mount_registration() -> None:
    """Clear mount-time config (tests only)."""
    global _URLCONF_IMPORTED, _URLCONF_IMPORT_DEFERRED, _URLCONF_IMPORTED_BEFORE_ADMIN
    from reflex_django.mount.auto import clear_auto_mount_state

    _REGISTRATIONS.clear()
    _URLCONF_IMPORTED = False
    _URLCONF_IMPORT_DEFERRED = False
    _URLCONF_IMPORTED_BEFORE_ADMIN = False
    clear_auto_mount_state()


def urlconf_was_imported_before_admin() -> bool:
    """Return whether ``ROOT_URLCONF`` was evaluated before admin autodiscover."""
    return _URLCONF_IMPORTED_BEFORE_ADMIN


def load_root_urlconf(*, reload_module: bool = False) -> None:
    """Import (or reload) ``ROOT_URLCONF`` and clear Django's URL resolver cache."""
    global _URLCONF_IMPORTED, _URLCONF_IMPORTED_BEFORE_ADMIN
    try:
        from django.conf import settings
    except Exception:
        return
    if not getattr(settings, "configured", False):
        return
    urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not isinstance(urlconf, str) or not urlconf.strip():
        return
    from importlib import import_module, reload
    import sys

    from django.contrib import admin
    from django.urls import clear_url_caches

    from reflex_django.mount.auto import should_defer_urlconf_import

    registry_empty = len(admin.site._registry) == 0
    try:
        if reload_module and urlconf in sys.modules:
            import_module(urlconf)
            reload(sys.modules[urlconf])
        else:
            import_module(urlconf)
        if registry_empty and should_defer_urlconf_import():
            _URLCONF_IMPORTED_BEFORE_ADMIN = True
        _URLCONF_IMPORTED = True
        clear_url_caches()
    except Exception:
        pass


def ensure_mount_config_loaded() -> None:
    """Import ``ROOT_URLCONF`` when Django is configured."""
    global _URLCONF_IMPORT_DEFERRED
    if _URLCONF_IMPORTED or _URLCONF_IMPORT_DEFERRED:
        return
    try:
        from django.apps import apps

        if not apps.ready:
            return
    except Exception:
        return
    try:
        from django.conf import settings
    except Exception:
        return
    if not getattr(settings, "configured", False):
        return
    if not getattr(settings, "ROOT_URLCONF", None):
        return

    from reflex_django.mount.auto import (
        admin_autodiscover_complete,
        should_defer_urlconf_import,
    )

    if should_defer_urlconf_import() and not admin_autodiscover_complete():
        _URLCONF_IMPORT_DEFERRED = True
    else:
        load_root_urlconf(reload_module=False)
