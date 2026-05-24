"""Django-first bootstrap: settings discovery and ``get_config`` patching."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any

from reflex_base.config import Config

from reflex_django.conf import configure_django
from reflex_django.project import RXCONFIG_SYNTHETIC_ATTR, discover_settings_module
from reflex_django.routing import UrlRoutingMode, resolve_url_routing

_INSTALLED = False
_ORIGINAL_GET_CONFIG: Callable[..., Config] | None = None


def call_original_get_config(reload: bool = False) -> Config:
    """Invoke Reflex's unpatched :func:`reflex_base.config.get_config`."""
    if _ORIGINAL_GET_CONFIG is None:
        from reflex_base.config import get_config

        return get_config(reload=reload)
    return _ORIGINAL_GET_CONFIG(reload=reload)


def _ensure_settings_env() -> None:
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        return
    discovered = discover_settings_module()
    if discovered:
        os.environ["DJANGO_SETTINGS_MODULE"] = discovered


def _patch_get_config() -> None:
    global _ORIGINAL_GET_CONFIG
    import reflex_base.config as config_module

    if _ORIGINAL_GET_CONFIG is not None:
        return
    _ORIGINAL_GET_CONFIG = config_module.get_config

    def patched_get_config(reload: bool = False) -> Config:
        if reload:
            sys.modules.pop("rxconfig", None)
        from reflex_django.rxconfig_bridge import build_merged_config_for_django_mode

        return build_merged_config_for_django_mode()

    config_module.get_config = patched_get_config  # type: ignore[method-assign]
    _rebind_get_config_imports(patched_get_config)


def _rebind_get_config_imports(patched_get_config: Callable[..., Config]) -> None:
    """Update modules that already imported ``get_config`` before patching."""
    for module_name in (
        "reflex.utils.prerequisites",
        "reflex.reflex",
        "reflex.app",
        "reflex.compiler.compiler",
        "reflex.utils.build",
        "reflex.utils.exec",
        "reflex.utils.path_ops",
        "reflex.utils.templates",
    ):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "get_config"):
            module.get_config = patched_get_config  # type: ignore[attr-defined]


def install_reflex_django_integration() -> None:
    """Bootstrap reflex-django for the current process (idempotent)."""
    global _INSTALLED

    _ensure_settings_env()
    configure_django()

    if _INSTALLED:
        _refresh_django_runtime()
        return

    _patch_get_config()
    _INSTALLED = True

    from reflex_django.cli_layout import ensure_reflex_cli_layout
    from reflex_django.mount_config import ensure_mount_config_loaded
    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_mount_config_loaded()
    ensure_reflex_cli_layout()
    ensure_rxconfig_from_django()
    if resolve_url_routing() == UrlRoutingMode.DJANGO_LED:
        from reflex_django.app_factory import ensure_django_led_app_ready

        ensure_django_led_app_ready()

    _patch_reflex_compile()
    _patch_assert_in_reflex_dir()
    _patch_needs_reinit()


def _refresh_django_runtime() -> None:
    """Re-apply Django rxconfig and rebind ``get_config`` after Reflex imports."""
    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_rxconfig_from_django()
    refresh_get_config_bindings()


def refresh_get_config_bindings() -> None:
    """Rebind ``get_config`` on Reflex modules loaded after the initial patch."""
    import reflex_base.config as config_module

    patched = config_module.get_config
    if patched is _ORIGINAL_GET_CONFIG:
        return
    _rebind_get_config_imports(patched)


def _patch_assert_in_reflex_dir() -> None:
    """Prepare layout instead of requiring a hand-written ``rxconfig.py``."""
    try:
        import reflex.utils.prerequisites as prerequisites
    except ImportError:
        return

    if getattr(prerequisites, "_reflex_django_assert_patched", False):
        return

    prerequisites._reflex_django_assert_original = prerequisites.assert_in_reflex_dir

    def patched_assert_in_reflex_dir() -> None:
        from reflex_django.cli_layout import ensure_reflex_cli_layout

        ensure_reflex_cli_layout()

    prerequisites.assert_in_reflex_dir = patched_assert_in_reflex_dir
    prerequisites._reflex_django_assert_patched = True


def _patch_needs_reinit() -> None:
    """Skip ``reflex init`` scaffolding; Django-first apps use ``reflex_mount()``."""
    try:
        import reflex.utils.prerequisites as prerequisites
    except ImportError:
        return

    if getattr(prerequisites, "_reflex_django_needs_reinit_patched", False):
        return

    original = prerequisites.needs_reinit

    def patched_needs_reinit() -> bool:
        from reflex_django.cli_layout import ensure_reflex_cli_layout

        ensure_reflex_cli_layout()
        return False

    prerequisites.needs_reinit = patched_needs_reinit
    prerequisites._reflex_django_needs_reinit_patched = True
    prerequisites._reflex_django_needs_reinit_original = original


def _patch_reflex_compile() -> None:
    """Compile in-process and restore the Vite Django dev proxy after compile."""
    try:
        import reflex.reflex as reflex_module
    except ImportError:
        return

    if getattr(reflex_module, "_reflex_django_compile_patched", False):
        return

    original_compile = reflex_module._compile_app

    def _compile_app(*, avoid_dirty_check: bool = True) -> None:
        result = original_compile(avoid_dirty_check=False)
        from reflex_django.vite_proxy import ensure_vite_django_dev_proxy_from_config

        ensure_vite_django_dev_proxy_from_config()
        return result

    reflex_module._compile_app = _compile_app  # type: ignore[assignment]
    reflex_module._reflex_django_compile_patched = True


def reset_integration_for_tests() -> None:
    """Restore unpatched ``get_config`` (tests only)."""
    global _INSTALLED, _ORIGINAL_GET_CONFIG
    if _ORIGINAL_GET_CONFIG is not None:
        import reflex_base.config as config_module

        config_module.get_config = _ORIGINAL_GET_CONFIG
    try:
        import reflex.utils.prerequisites as prerequisites

        original = getattr(prerequisites, "_reflex_django_assert_original", None)
        if original is not None:
            prerequisites.assert_in_reflex_dir = original
            prerequisites._reflex_django_assert_patched = False
        reinit_original = getattr(
            prerequisites, "_reflex_django_needs_reinit_original", None
        )
        if reinit_original is not None:
            prerequisites.needs_reinit = reinit_original
            prerequisites._reflex_django_needs_reinit_patched = False
    except ImportError:
        pass
    mod = sys.modules.get("rxconfig")
    if mod is not None and getattr(mod, RXCONFIG_SYNTHETIC_ATTR, False):
        sys.modules.pop("rxconfig", None)
    _INSTALLED = False
    _ORIGINAL_GET_CONFIG = None
