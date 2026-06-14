"""Django-first bootstrap: settings discovery and ``get_config`` patching."""

from __future__ import annotations

from reflex_base.config import Config

from reflex_django.setup.conf import configure_django
from reflex_django.setup.project import RXCONFIG_SYNTHETIC_ATTR, discover_settings_module

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
    _patch_assert_in_reflex_dir,
    _patch_get_config,
    _patch_needs_reinit,
    _patch_prerequisites_app_module,
    _patch_reload_paths,
    _patch_state_dispatcher_template,
    _patch_vite_dev_dependency,
    _rebind_get_config_imports,
    get_original_get_config,
    install_bootstrap_patches,
    install_post_rxconfig_patches,
    is_installed,
    refresh_get_config_bindings,
    set_installed,
    uninstall_all_patches,
)

__all__ = [
    "call_original_get_config",
    "install_reflex_django_integration",
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


def install_reflex_django_integration() -> None:
    """Bootstrap reflex-django for the current process (idempotent)."""
    _ensure_settings_env()
    configure_django()
    _ensure_runtime_event_patches()

    if is_installed():
        _refresh_django_runtime()
        _materialize_reflex_app_module_stub()
        return

    install_bootstrap_patches()

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
    mod = sys.modules.get("rxconfig")
    if mod is not None and getattr(mod, RXCONFIG_SYNTHETIC_ATTR, False):
        sys.modules.pop("rxconfig", None)
    set_installed(False)
