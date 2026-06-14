"""Reflex ``rx.Config`` registration from :func:`reflex_django.django.urls.reflex_mount`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_URLCONF_IMPORTED = False


@dataclass(frozen=True)
class MountRxConfigRegistration:
    """Plugins, prefixes, and ``rx.Config`` overrides from a ``reflex_mount()`` call."""

    plugins: tuple[Any, ...] = ()
    rx_config: dict[str, Any] = field(default_factory=dict)
    django_plugin: dict[str, Any] = field(default_factory=dict)
    mount_prefix: str | None = None
    django_prefix: tuple[str, ...] | None = None
    app_name: str | None = None


_REGISTRATIONS: list[MountRxConfigRegistration] = []


def default_app_name_from_project() -> str:
    """Derive a Reflex app name from the Django project directory (``manage.py`` parent)."""
    from reflex_django.setup.project import find_manage_py

    manage = find_manage_py()
    root = manage.parent if manage is not None else Path.cwd()
    name = root.name.replace("-", "_")
    if name == "reflex_django":
        # Running from the library checkout must not import ``reflex_django.reflex_django``.
        return "web"
    return name


def register_mount_rx_config(
    *,
    app_name: str | None = None,
    plugins: Sequence[Any] | None = None,
    rx_config: Mapping[str, Any] | None = None,
    django_plugin: Mapping[str, Any] | None = None,
    mount_prefix: str | None = None,
    django_prefix: str | tuple[str, ...] | None = None,
) -> None:
    """Record Reflex config from :func:`reflex_django.django.urls.reflex_mount` (idempotent merge)."""
    coerced_django: tuple[str, ...] | None = None
    if django_prefix is not None:
        if isinstance(django_prefix, str):
            coerced_django = (django_prefix,) if django_prefix.strip() else ()
        else:
            coerced_django = tuple(str(p) for p in django_prefix if str(p).strip())

    _REGISTRATIONS.append(
        MountRxConfigRegistration(
            app_name=app_name,
            plugins=tuple(plugins or ()),
            rx_config=dict(rx_config or {}),
            django_plugin=dict(django_plugin or {}),
            mount_prefix=mount_prefix,
            django_prefix=coerced_django,
        )
    )


def get_merged_mount_rx_config() -> MountRxConfigRegistration:
    """Merge all ``reflex_mount()`` registrations (plugins de-duplicated by identity)."""
    merged_plugins: list[Any] = []
    merged_rx: dict[str, Any] = {}
    merged_django: dict[str, Any] = {}
    mount_prefix: str | None = None
    django_prefix: tuple[str, ...] | None = None
    app_name: str | None = None
    for registration in _REGISTRATIONS:
        for plugin in registration.plugins:
            if plugin not in merged_plugins:
                merged_plugins.append(plugin)
        merged_rx.update(registration.rx_config)
        merged_django.update(registration.django_plugin)
        if registration.mount_prefix is not None:
            mount_prefix = registration.mount_prefix
        if registration.django_prefix is not None:
            django_prefix = registration.django_prefix
        if registration.app_name is not None:
            app_name = registration.app_name
    for plugin in _resolve_plugins_from_settings():
        if plugin not in merged_plugins:
            merged_plugins.append(plugin)
    settings_rx = _settings_rx_config()
    for key, value in settings_rx.items():
        if key not in merged_rx:
            merged_rx[key] = value
    return MountRxConfigRegistration(
        app_name=app_name,
        plugins=tuple(merged_plugins),
        rx_config=merged_rx,
        django_plugin=merged_django,
        mount_prefix=mount_prefix,
        django_prefix=django_prefix,
    )


def resolve_app_name() -> str:
    """Return Reflex ``app_name`` from settings, mount registration, or project folder."""
    settings_rx = _settings_rx_config()
    settings_name = settings_rx.get("app_name")
    if isinstance(settings_name, str) and settings_name.strip():
        return settings_name.strip()

    ensure_mount_config_loaded()
    mount = get_merged_mount_rx_config()
    if mount.app_name and str(mount.app_name).strip():
        return str(mount.app_name).strip()
    rx_name = mount.rx_config.get("app_name")
    if isinstance(rx_name, str) and rx_name.strip():
        return rx_name.strip()
    return default_app_name_from_project()


def _settings_rx_config() -> dict[str, Any]:
    from reflex_django.setup.rxconfig_bridge import _coerce_rx_config_dict

    try:
        from django.conf import settings
    except Exception:
        return {}
    raw = getattr(settings, "RX_CONFIG", None)
    if not raw:
        return {}
    return _coerce_rx_config_dict(dict(raw))


def _resolve_plugins_from_settings() -> tuple[Any, ...]:
    try:
        from django.conf import settings
        from django.utils.module_loading import import_string
    except Exception:
        return ()

    entries = getattr(settings, "RX_PLUGINS", None) or ()
    resolved: list[Any] = []
    for entry in entries:
        if isinstance(entry, str) and entry.strip():
            resolved.append(import_string(entry.strip())())
        else:
            resolved.append(entry)
    return tuple(resolved)


def get_mount_rx_config_overrides() -> dict[str, Any]:
    """Merged ``rx.Config`` keyword arguments from settings and ``reflex_mount()``."""
    from reflex_django.runtime.app_factory import reflex_app_module_import
    from reflex_django.setup.rxconfig_bridge import _coerce_rx_config_dict

    ensure_mount_config_loaded()
    mount = get_merged_mount_rx_config()
    kwargs = _coerce_rx_config_dict(mount.rx_config or None)
    settings_rx = _settings_rx_config()
    for key, value in settings_rx.items():
        if key not in kwargs:
            kwargs[key] = value
    kwargs.setdefault("app_name", resolve_app_name())
    kwargs.setdefault("app_module_import", reflex_app_module_import())
    return kwargs


def has_mount_rx_config() -> bool:
    """Return whether :func:`reflex_django.django.urls.reflex_mount` has registered config."""
    return bool(_REGISTRATIONS)


def clear_mount_rx_config() -> None:
    """Clear mount-time config (tests only)."""
    global _URLCONF_IMPORTED
    from reflex_django.mount.auto import clear_auto_mount_state

    _REGISTRATIONS.clear()
    _URLCONF_IMPORTED = False
    clear_auto_mount_state()


def ensure_mount_config_loaded() -> None:
    """Import ``ROOT_URLCONF`` and ensure mount config is registered from settings."""
    global _URLCONF_IMPORTED
    if _URLCONF_IMPORTED:
        if not has_mount_rx_config():
            from reflex_django.mount.auto import register_mount_from_settings

            register_mount_from_settings()
        return
    try:
        from django.conf import settings
    except Exception:
        return
    if not getattr(settings, "configured", False):
        return
    urlconf = getattr(settings, "ROOT_URLCONF", None)
    if not urlconf:
        return
    try:
        from importlib import import_module

        import_module(urlconf)
        _URLCONF_IMPORTED = True
    except Exception:
        pass
    if not has_mount_rx_config():
        from reflex_django.mount.auto import register_mount_from_settings

        register_mount_from_settings()
