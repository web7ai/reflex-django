"""Build and merge ``rx.Config`` from Django settings (Django-first projects)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

from reflex_base.config import Config

from reflex_django.setup.plugin import ReflexDjangoPlugin
from reflex_django.setup.project import find_manage_py, rxconfig_path

_RXCONFIG_MODULE = "rxconfig"
_RXCONFIG_STUB_MARKER = "reflex-django Django-first mode"
_RXCONFIG_STUB_HEADER = f'''\
"""Stub ``rxconfig`` for {_RXCONFIG_STUB_MARKER}.

Reflex reads this file for project layout checks. Live settings come from Django
(``reflex_mount(app_name=..., rx_config=...)``) and are merged at
runtime by reflex-django. You may edit or delete this file if you maintain your
own ``rxconfig.py`` instead.
"""
import reflex as rx

config = rx.Config(
    app_name={{app_name!r}},
    app_module_import={{app_module_import!r}},
)
'''


def _format_rxconfig_stub(*, app_name: str, app_module_import: str) -> str:
    return _RXCONFIG_STUB_HEADER.format(
        app_name=app_name,
        app_module_import=app_module_import,
    )


def is_django_first_rxconfig_stub(path: Path | None = None) -> bool:
    """Return whether *path* is an auto-generated reflex-django stub (not user-owned)."""
    target = path or rxconfig_path()
    if target is None:
        return False
    try:
        return _RXCONFIG_STUB_MARKER in target.read_text(encoding="utf-8")
    except OSError:
        return False

# Safe ``rx.Config`` fields users may set via ``reflex_mount(..., rx_config={...})``.
ALLOWED_RX_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "app_name",
        "app_module_import",
        "loglevel",
        "frontend_port",
        "frontend_path",
        "backend_port",
        "backend_path",
        "api_url",
        "deploy_url",
        "backend_host",
        "db_url",
        "async_db_url",
        "redis_url",
        "telemetry_enabled",
        "bun_path",
        "static_page_generation_timeout",
        "cors_allowed_origins",
        "vite_allowed_hosts",
        "react_strict_mode",
        "frontend_packages",
        "state_manager_mode",
        "redis_lock_expiration",
        "redis_lock_warning_threshold",
        "redis_token_expiration",
        "env_file",
        "state_auto_setters",
        "show_built_with_reflex",
        "is_reflex_cloud",
        "extra_overlay_function",
        "disable_plugins",
        "transport",
    }
)


def _django_settings() -> Any:
    from django.conf import settings

    return settings


def _coerce_rx_config_dict(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if not isinstance(raw, dict):
        msg = "rx_config must be a dict of rx.Config keyword arguments."
        raise TypeError(msg)
    unknown = set(raw) - ALLOWED_RX_CONFIG_KEYS
    if unknown:
        msg = (
            f"Unsupported rx_config keys: {sorted(unknown)}. "
            f"Use reflex_mount(plugins=[...]) and django_plugin={{...}} for plugins."
        )
        raise ValueError(msg)
    if "plugins" in raw:
        msg = (
            "rx_config cannot set 'plugins'. "
            "Use reflex_mount(plugins=[...]) instead."
        )
        raise ValueError(msg)
    return dict(raw)


def _should_use_rxconfig_file() -> bool:
    """Return whether to load an on-disk ``rxconfig.py`` instead of ``reflex_mount()``."""
    settings = _django_settings()
    explicit = getattr(settings, "RX_USE_RXCONFIG_FILE", None)
    if explicit is not None:
        return bool(explicit)
    if is_django_first_rxconfig_stub(rxconfig_path()):
        return False
    return False


def load_rxconfig_file_if_present() -> Config | None:
    """Load ``rxconfig.py`` via Reflex when allowed by Django settings."""
    if not _should_use_rxconfig_file():
        return None
    if rxconfig_path() is None:
        return None
    from reflex_django.runtime.integration import call_original_get_config

    return call_original_get_config()


def build_rx_config_from_django() -> Config:
    """Synthesize ``rx.Config`` from :func:`reflex_django.django.urls.reflex_mount` registration."""
    from reflex_django.mount.config import get_mount_rx_config_overrides

    return Config(_skip_plugins_checks=True, **get_mount_rx_config_overrides())


def merge_rx_config(
    base: Config,
    overrides: dict[str, Any],
    *,
    override: bool,
) -> Config:
    """Merge *overrides* into *base* in place (Reflex Config is not a plain dataclass)."""
    if not overrides:
        return base

    for key, value in overrides.items():
        if key not in ALLOWED_RX_CONFIG_KEYS:
            continue
        current = getattr(base, key, None)
        if override or current in (None, "", ()):
            setattr(base, key, value)
    return base


def _has_reflex_django_plugin(plugins: Any) -> bool:
    if not plugins:
        return False
    return any(isinstance(p, ReflexDjangoPlugin) for p in plugins)


def _merge_mount_plugins(config: Config) -> Config:
    """Apply plugins registered via :func:`reflex_django.django.urls.reflex_mount`."""
    from reflex_django.mount.config import ensure_mount_config_loaded, get_merged_mount_rx_config

    ensure_mount_config_loaded()
    mount = get_merged_mount_rx_config()
    if not mount.plugins:
        return config

    plugins = list(config.plugins or ())
    for plugin in mount.plugins:
        if plugin not in plugins:
            plugins.append(plugin)
    config.plugins = tuple(plugins)
    return config


def ensure_reflex_django_plugin(config: Config) -> Config:
    """No-op in v1.0 — ReflexDjangoPlugin was removed."""
    return config


def install_rxconfig_module(config: Config) -> None:
    """Register *config* on ``sys.modules['rxconfig']`` for Reflex caching."""
    from reflex_django.setup.project import RXCONFIG_SYNTHETIC_ATTR

    mod = sys.modules.get(_RXCONFIG_MODULE)
    if mod is None:
        mod = types.ModuleType(_RXCONFIG_MODULE)
        sys.modules[_RXCONFIG_MODULE] = mod
    setattr(mod, RXCONFIG_SYNTHETIC_ATTR, True)
    mod.config = config  # type: ignore[attr-defined]


def _apply_built_with_reflex_default(config: Config) -> Config:
    """Force the "Built with Reflex" badge off unless the user opted in.

    Reflex's upstream default for ``show_built_with_reflex`` is ``True``.
    Django-first reflex-django projects almost always ship their own
    branding, so we flip the default to ``False``. The flip is gated by the
    Django setting :data:`RX_SHOW_BUILT_WITH_REFLEX` (default
    ``False``) and only applies when:

    - The user has not already set ``show_built_with_reflex`` to ``False``
      explicitly (we leave their ``False`` alone — same outcome).
    - The user has not explicitly set it to ``True`` via
      ``reflex_mount(rx_config={"show_built_with_reflex": True})`` AND the
      setting is also ``True`` (in which case they explicitly opted in).

    In effect: by default everyone sees ``show_built_with_reflex=False``;
    flipping the Django setting to ``True`` restores Reflex's upstream
    default for that project.
    """
    settings = _django_settings()
    desired = bool(
        getattr(settings, "RX_SHOW_BUILT_WITH_REFLEX", False)
    )
    # Respect a user who has explicitly opted in via reflex_mount(rx_config=...)
    # by checking the mount overrides — if they passed it through there,
    # honor that. Otherwise our default wins.
    from reflex_django.mount.config import get_mount_rx_config_overrides

    overrides = get_mount_rx_config_overrides()
    if "show_built_with_reflex" in overrides:
        return config  # already merged in by ``apply_django_rx_config`` caller
    try:
        setattr(config, "show_built_with_reflex", desired)
    except Exception:  # noqa: BLE001
        # ``rx.Config`` may make this attribute read-only in future versions
        # — log silently rather than blocking config assembly.
        pass
    return config


def apply_django_rx_config(config: Config) -> Config:
    """Apply ``reflex_mount()`` rx settings onto *config*."""
    from reflex_django.mount.config import get_mount_rx_config_overrides

    mount_overrides = get_mount_rx_config_overrides()
    merged = merge_rx_config(config, mount_overrides, override=True)
    merged = _merge_mount_plugins(merged)
    merged = ensure_reflex_django_plugin(merged)
    merged = _apply_built_with_reflex_default(merged)
    install_rxconfig_module(merged)
    return merged


def remove_django_first_rxconfig_stub() -> bool:
    """Delete an auto-generated stub ``rxconfig.py`` (Django-first uses ``reflex_mount``).

    Only removes files that contain the reflex-django stub marker. User-owned
    ``rxconfig.py`` files are never touched.

    Returns:
        ``True`` if a stub file was deleted.
    """
    if getattr(_django_settings(), "RX_MATERIALIZE_RXCONFIG", False):
        return False
    target = rxconfig_path()
    if target is None or not is_django_first_rxconfig_stub(target):
        return False
    target.unlink()
    return True


def ensure_rxconfig_file(*, for_cli: bool = False) -> Path | None:
    """Materialize ``rxconfig.py`` on disk when explicitly requested.

    ``run_reflex`` does **not** call this with ``for_cli=True`` anymore; config is
    registered in memory via :func:`install_rxconfig_module`. This function only runs
    when ``RX_MATERIALIZE_RXCONFIG`` is ``True`` (or legacy
    ``for_cli=True`` with materialize enabled).

    Args:
        for_cli: Ignored unless ``RX_MATERIALIZE_RXCONFIG`` is ``True``.

    Returns:
        Path to ``rxconfig.py`` when written or updated, else ``None``.

    """
    del for_cli
    settings = _django_settings()
    if not getattr(settings, "RX_MATERIALIZE_RXCONFIG", False):
        return None

    from reflex_django.runtime.app_factory import reflex_app_module_import
    from reflex_django.mount.config import ensure_mount_config_loaded, resolve_app_name

    ensure_mount_config_loaded()
    app_name = resolve_app_name()
    app_module_import = reflex_app_module_import()
    body = _format_rxconfig_stub(
        app_name=app_name,
        app_module_import=app_module_import,
    )

    manage_py = find_manage_py()
    root = manage_py.parent if manage_py is not None else Path.cwd()
    target = root / "rxconfig.py"

    if target.is_file():
        if not is_django_first_rxconfig_stub(target):
            return None
        if target.read_text(encoding="utf-8") == body:
            return None
        target.write_text(body, encoding="utf-8")
        return target

    target.write_text(body, encoding="utf-8")
    return target


def build_merged_config_for_django_mode() -> Config:
    """Build Reflex config from Django settings and register ``sys.modules['rxconfig']``.

    Does not require ``rxconfig.py`` on disk unless
    ``RX_MATERIALIZE_RXCONFIG`` / ``RX_USE_RXCONFIG_FILE`` are enabled.
    """
    settings = _django_settings()
    if getattr(settings, "RX_MATERIALIZE_RXCONFIG", False):
        ensure_rxconfig_file()

    if _should_use_rxconfig_file() and rxconfig_path() is not None:
        from reflex_django.runtime.integration import call_original_get_config

        base = call_original_get_config()
    else:
        base = build_rx_config_from_django()

    return apply_django_rx_config(base)


def ensure_rxconfig_from_django() -> Config:
    """Load Reflex :class:`~reflex_base.config.Config` from Django (ASGI / ``settings.py``).

    Same as :func:`build_merged_config_for_django_mode` — use from ``asgi.py`` bootstrap
    when you do not keep ``rxconfig.py`` in the project tree.
    """
    return build_merged_config_for_django_mode()
