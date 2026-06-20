"""Plugin-only bootstrap for reflex-django."""

from __future__ import annotations

import logging
import os
from typing import Any

from reflex_base.config import Config

from reflex_django.setup.conf import configure_django

from reflex_django.runtime.integration.detect import detect_reflex_django_plugin
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
    get_original_get_config,
    install_bootstrap_patches,
    install_runtime_patches,
    is_installed,
    set_installed,
    uninstall_all_patches,
)

logger = logging.getLogger("reflex_django.runtime.integration")

_BOOTSTRAP_IN_PROGRESS = False

__all__ = [
    "call_original_get_config",
    "install_plugin_integration",
    "install_reflex_django_integration",
    "reset_integration_for_tests",
    "_ensure_runtime_event_patches",
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


def _ensure_runtime_event_patches() -> None:
    """Apply hooks so ``self.request`` works on handler substates (idempotent)."""
    _patch_process_event()
    _patch_event_context_emit_delta()
    _patch_basestate_getstate()


def _apply_plugin_settings_module(plugin: Any) -> None:
    settings_module = (getattr(plugin, "config", None) or {}).get("settings_module")
    if isinstance(settings_module, str) and settings_module.strip():
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module.strip())


def install_plugin_integration(plugin: Any) -> None:
    """Bootstrap reflex-django when ``ReflexDjangoPlugin`` is in ``rxconfig.py``."""
    global _BOOTSTRAP_IN_PROGRESS
    if is_installed() or _BOOTSTRAP_IN_PROGRESS:
        return
    _BOOTSTRAP_IN_PROGRESS = True
    try:
        _apply_plugin_settings_module(plugin)
        _ensure_settings_env()

        from reflex_django.mount.config import (
            ensure_mount_config_loaded,
            register_mount_from_plugin,
        )
        from reflex_django.mount.integration_config import (
            IntegrationConfig,
            mount_enabled,
            resolve_and_cache_integration_config,
            set_integration_config,
        )

        # Cache plugin intent before django.setup() so AdminConfig.ready and other
        # hooks respect mount.enabled=False during bootstrap.
        early = IntegrationConfig.from_plugin(plugin)
        early.validate(runtime=False)
        set_integration_config(early)

        configure_django()
        _ensure_runtime_event_patches()
        install_bootstrap_patches(patch_get_config=False)

        integration = resolve_and_cache_integration_config(plugin)
        register_mount_from_plugin(plugin)
        ensure_mount_config_loaded()

        if mount_enabled():
            from reflex_django.mount.auto import maybe_auto_mount

            maybe_auto_mount()
        else:
            logger.info(
                "reflex-django: mount.enabled=False — skipping reflex_mount auto-mount."
            )

        install_runtime_patches()
        set_installed(True)
        logger.info(
            "reflex-django: plugin integration active (%s). "
            "Use reflex run / reflex export.",
            integration.summary(),
        )
    finally:
        _BOOTSTRAP_IN_PROGRESS = False


def install_reflex_django_integration() -> None:
    """Bootstrap reflex-django if ``ReflexDjangoPlugin`` is present in on-disk ``rxconfig``."""
    if _BOOTSTRAP_IN_PROGRESS or is_installed():
        return
    config = call_original_get_config(reload=False)
    plugin = detect_reflex_django_plugin(config)
    if plugin is not None:
        install_plugin_integration(plugin)


def reset_integration_for_tests() -> None:
    """Restore unpatched Reflex hooks (tests only)."""
    uninstall_all_patches()
    set_installed(False)
