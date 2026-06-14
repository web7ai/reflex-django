"""Django-first and Reflex-first bootstrap: settings discovery and ``get_config`` patching."""

from __future__ import annotations

import logging
import os
from typing import Any

from reflex_base.config import Config

from reflex_django.setup.conf import configure_django
from reflex_django.setup.project import RXCONFIG_SYNTHETIC_ATTR, discover_settings_module

from reflex_django.runtime.integration.modes import (
    IntegrationMode,
    clear_active_integration_mode,
    resolve_integration_mode,
    set_active_integration_mode,
)
from reflex_django.runtime.integration.patches.basestate import (
    _DJANGO_TRANSIENT_STATE_ATTRS,
    _patch_basestate_getstate,
)
from reflex_django.runtime.integration.patches.compile import (
    _finalize_web_dev_layout_safe,
    _patch_app_compile,
    _patch_compile_or_validate_app,
    _patch_reflex_compile,
    _patch_vite_config_generation,
)
from reflex_django.runtime.integration.patches.events import (
    _patch_event_context_emit_delta,
    _patch_process_event,
)
from reflex_django.runtime.integration.patches.pages import (
    _patch_apply_decorated_pages,
    _patch_reflex_page,
    _reflex_page_namespace,
    _resolve_decorated_pages_app_name,
)
from reflex_django.runtime.integration.registry import (
    _ensure_settings_env,
    _rebind_get_config_imports,
    get_original_get_config,
    install_bootstrap_patches,
    install_post_rxconfig_patches,
    is_installed,
    refresh_get_config_bindings,
    set_installed,
    uninstall_all_patches,
)

logger = logging.getLogger("reflex_django.runtime.integration")

_BOOTSTRAP_IN_PROGRESS = False

__all__ = [
    "call_original_get_config",
    "install_django_first_integration",
    "install_reflex_django_integration",
    "install_reflex_first_integration",
    "reset_integration_for_tests",
    "refresh_get_config_bindings",
    "_ensure_runtime_event_patches",
    "_rebind_get_config_imports",
    "_DJANGO_TRANSIENT_STATE_ATTRS",
    "_patch_basestate_getstate",
    "_patch_process_event",
    "_patch_event_context_emit_delta",
    "_reflex_page_namespace",
    "_resolve_decorated_pages_app_name",
    "_patch_reflex_page",
    "_patch_apply_decorated_pages",
    "_finalize_web_dev_layout_safe",
    "_patch_vite_config_generation",
    "_patch_app_compile",
    "_patch_compile_or_validate_app",
    "_patch_reflex_compile",
]


def call_original_get_config(reload: bool = False) -> Config:
    """Invoke Reflex's unpatched :func:`reflex_base.config.get_config`."""
    original = get_original_get_config()
    if original is None:
        from reflex_base.config import get_config

        return get_config(reload=reload)
    return original(reload=reload)


def _materialize_reflex_app_module_stub() -> None:
    from reflex_django.runtime.app_factory import ensure_reflex_app_module_stub

    ensure_reflex_app_module_stub()


def _ensure_runtime_event_patches() -> None:
    """Apply hooks so ``self.request`` works on handler substates (idempotent)."""
    _patch_process_event()
    _patch_event_context_emit_delta()
    _patch_basestate_getstate()


def _apply_plugin_settings_module(plugin: Any) -> None:
    settings_module = (getattr(plugin, "config", None) or {}).get("settings_module")
    if isinstance(settings_module, str) and settings_module.strip():
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module.strip())


def install_reflex_first_integration(plugin: Any) -> None:
    """Bootstrap reflex-django for Reflex-first projects (``ReflexDjangoPlugin``)."""
    global _BOOTSTRAP_IN_PROGRESS
    if is_installed() or _BOOTSTRAP_IN_PROGRESS:
        return
    _BOOTSTRAP_IN_PROGRESS = True
    try:
        _apply_plugin_settings_module(plugin)
        _ensure_settings_env()
        configure_django()
        _ensure_runtime_event_patches()
        install_bootstrap_patches(patch_get_config=False)

        from reflex_django.mount.config import (
            ensure_mount_config_loaded,
            register_mount_from_plugin,
        )

        register_mount_from_plugin(plugin)
        ensure_mount_config_loaded()

        urlconf = (getattr(plugin, "config", None) or {}).get("urlconf")
        if isinstance(urlconf, str) and urlconf.strip():
            from importlib import import_module

            import_module(urlconf.strip())

        auto_mount = (getattr(plugin, "config", None) or {}).get("auto_mount", True)
        if auto_mount is not False:
            from reflex_django.mount.auto import maybe_auto_mount

            maybe_auto_mount()

        install_post_rxconfig_patches()
        set_active_integration_mode(IntegrationMode.REFLEX_FIRST)
        set_installed(True)
        logger.info(
            "reflex-django: Reflex-first mode active via ReflexDjangoPlugin. "
            "Use reflex run / reflex export; Django routes mount in the Reflex backend."
        )
    finally:
        _BOOTSTRAP_IN_PROGRESS = False


def install_django_first_integration() -> None:
    """Bootstrap reflex-django for Django-first projects (settings-driven config)."""
    global _BOOTSTRAP_IN_PROGRESS
    if is_installed():
        _refresh_django_runtime()
        _materialize_reflex_app_module_stub()
        return
    if _BOOTSTRAP_IN_PROGRESS:
        return
    _BOOTSTRAP_IN_PROGRESS = True
    try:
        _ensure_settings_env()
        configure_django()
        _ensure_runtime_event_patches()
        from reflex_django.runtime.integration.registry import (
            _install_smart_get_config_patch,
            install_bootstrap_patches,
        )

        _install_smart_get_config_patch()
        install_bootstrap_patches(patch_get_config=False)
        from reflex_django.cli.layout import ensure_reflex_cli_layout
        from reflex_django.mount.config import ensure_mount_config_loaded
        from reflex_django.runtime.app_factory import get_or_create_app
        from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django

        ensure_mount_config_loaded()
        from reflex_django.mount.auto import maybe_auto_mount

        maybe_auto_mount()
        get_or_create_app()
        ensure_reflex_cli_layout()
        ensure_rxconfig_from_django()
        from reflex_django.bootstrap.patches.registry import apply_post_rxconfig_patches

        apply_post_rxconfig_patches()
        _materialize_reflex_app_module_stub()
        set_active_integration_mode(IntegrationMode.DJANGO_FIRST)
        set_installed(True)
    finally:
        _BOOTSTRAP_IN_PROGRESS = False


def install_reflex_django_integration(
    *,
    mode: IntegrationMode | None = None,
) -> None:
    """Bootstrap reflex-django for the current process (idempotent)."""
    if _BOOTSTRAP_IN_PROGRESS:
        return
    resolved = mode or resolve_integration_mode()
    set_active_integration_mode(resolved)

    if resolved == IntegrationMode.REFLEX_FIRST:
        config = call_original_get_config(reload=False)
        from reflex_django.runtime.integration.modes import detect_reflex_django_plugin

        plugin = detect_reflex_django_plugin(config)
        if plugin is not None:
            install_reflex_first_integration(plugin)
        return

    if resolved == IntegrationMode.DJANGO_FIRST:
        _ensure_settings_env()
        configure_django()
        _ensure_runtime_event_patches()
        install_django_first_integration()
        return

    if not is_installed():
        set_installed(True)


def _refresh_django_runtime() -> None:
    """Re-apply Django rxconfig and rebind ``get_config`` after Reflex imports."""
    from reflex_django.setup.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_rxconfig_from_django()
    refresh_get_config_bindings()


def reset_integration_for_tests() -> None:
    """Restore unpatched ``get_config`` (tests only)."""
    import sys

    uninstall_all_patches()
    clear_active_integration_mode()
    mod = sys.modules.get("rxconfig")
    if mod is not None and getattr(mod, RXCONFIG_SYNTHETIC_ATTR, False):
        sys.modules.pop("rxconfig", None)
    set_installed(False)
