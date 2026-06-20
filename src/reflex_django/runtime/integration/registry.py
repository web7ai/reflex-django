"""Patch registry: install/uninstall and original callables."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from reflex_base.config import Config

from reflex_django.setup.project import discover_settings_module

_INSTALLED = False
_ORIGINAL_GET_RELOAD_PATHS: Callable[[], Any] | None = None


def is_installed() -> bool:
    return _INSTALLED


def set_installed(value: bool) -> None:
    global _INSTALLED
    _INSTALLED = value


def get_original_get_config() -> Callable[..., Config] | None:
    from reflex_django.runtime.get_config_patch import get_original_get_config as _orig

    return _orig()


def _ensure_settings_env() -> None:
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        return
    discovered = discover_settings_module()
    if discovered:
        os.environ["DJANGO_SETTINGS_MODULE"] = discovered


def _install_plugin_get_config_patch() -> None:
    """Wrap Reflex ``get_config`` to bootstrap plugin integration on first load."""
    from reflex_django.runtime.get_config_patch import install_plugin_get_config_patch

    install_plugin_get_config_patch()


def _rebind_get_config_imports(patched_get_config: Callable[..., Config]) -> None:
    """Update modules that already imported ``get_config`` before patching."""
    from reflex_django.runtime.get_config_patch import (
        _rebind_get_config_imports as _rebind,
    )

    _rebind(patched_get_config)


def _patch_reload_paths() -> None:
    """Watch Django ``BASE_DIR`` for HMR."""
    global _ORIGINAL_GET_RELOAD_PATHS
    try:
        import reflex.utils.exec as exec_module
    except ImportError:
        return

    if _ORIGINAL_GET_RELOAD_PATHS is not None:
        return

    _ORIGINAL_GET_RELOAD_PATHS = exec_module.get_reload_paths

    def patched_get_reload_paths() -> Any:
        from reflex_django.dev.watch import plugin_reload_paths

        return plugin_reload_paths()

    exec_module.get_reload_paths = patched_get_reload_paths  # type: ignore[assignment]


def _patch_vite_dev_dependency() -> None:
    """Opt-in override for the ``vite`` devDependency Reflex pins."""
    desired: str | None = None

    try:
        from django.conf import settings as django_settings

        candidate = getattr(django_settings, "RX_VITE_VERSION", None)
        if isinstance(candidate, str) and candidate.strip():
            desired = candidate.strip()
    except Exception:  # noqa: BLE001
        pass

    if desired is None:
        env_value = os.environ.get("RX_VITE_VERSION", "").strip()
        if env_value:
            desired = env_value

    if desired is None:
        return

    try:
        from reflex_base.constants.installer import PackageJson
    except ImportError:
        return

    dev_deps = getattr(PackageJson, "DEV_DEPENDENCIES", None)
    if not isinstance(dev_deps, dict):
        return
    if dev_deps.get("vite") == desired:
        return
    dev_deps["vite"] = desired


_STATE_DISPATCHER_MARKER = "/* reflex-django: tolerant dispatcher */"

_STATE_DISPATCHER_ORIGINAL = (
    "      for (const substate in update.delta) {\n"
    "        dispatch[substate](update.delta[substate]);"
)

_STATE_DISPATCHER_PATCHED = (
    "      for (const substate in update.delta) {\n"
    f"        {_STATE_DISPATCHER_MARKER}\n"
    "        const _rxdj_dispatch = dispatch[substate];\n"
    '        if (typeof _rxdj_dispatch !== "function") {\n'
    '          if (typeof console !== "undefined" && console.warn) {\n'
    "            console.warn(\n"
    '              "[reflex-django] No dispatcher for substate \'" + substate + "\' — "\n'
    '              + "skipping delta. Re-run `reflex export` to regenerate. Known dispatchers: "\n'
    '              + Object.keys(dispatch).join(", "),\n'
    "            );\n"
    "          }\n"
    "          continue;\n"
    "        }\n"
    "        _rxdj_dispatch(update.delta[substate]);"
)


def _patch_state_dispatcher_template() -> None:
    """Make the generated ``utils/state.js`` tolerant of unknown substates."""
    from pathlib import Path

    template_path: Path | None = None
    try:
        import reflex_base

        template_path = (
            Path(reflex_base.__file__).parent
            / ".templates"
            / "web"
            / "utils"
            / "state.js"
        )
    except Exception:  # noqa: BLE001
        return

    if template_path is None or not template_path.exists():
        return

    try:
        source = template_path.read_text(encoding="utf-8")
    except OSError:
        return

    if _STATE_DISPATCHER_MARKER in source:
        return
    if _STATE_DISPATCHER_ORIGINAL not in source:
        return

    patched = source.replace(_STATE_DISPATCHER_ORIGINAL, _STATE_DISPATCHER_PATCHED, 1)

    try:
        template_path.write_text(patched, encoding="utf-8")
    except OSError:
        logging.getLogger("reflex_django.runtime.integration.registry").warning(
            "Could not patch %s for tolerant dispatcher; readonly site-packages?",
            template_path,
        )


def install_bootstrap_patches(*, patch_get_config: bool = True) -> None:
    """Apply early patches before compile."""
    if patch_get_config:
        _install_plugin_get_config_patch()
    _patch_reload_paths()
    _patch_vite_dev_dependency()
    _patch_state_dispatcher_template()


def install_runtime_patches() -> None:
    """Apply compile and page patches after ``rxconfig`` is available."""
    from reflex_django.runtime.integration.patches.compile import (
        _patch_app_compile,
        _patch_reflex_compile,
        _patch_vite_config_generation,
    )
    from reflex_django.runtime.integration.patches.pages import (
        _patch_apply_decorated_pages,
        _patch_reflex_page,
    )

    _patch_vite_config_generation()
    _patch_app_compile()
    _patch_reflex_compile()
    _patch_reflex_page()
    _patch_apply_decorated_pages()

    # Warn (don't fail) if Reflex is outside the supported range or a patched
    # internal has moved, so upgrades surface loudly instead of breaking quietly.
    try:
        from reflex_django.core.compat import warn_if_unsupported_reflex

        warn_if_unsupported_reflex()
    except Exception:
        pass


# Alias used by plugin lifecycle hooks
install_post_rxconfig_patches = install_runtime_patches


def uninstall_all_patches() -> None:
    """Restore unpatched Reflex hooks."""
    global _ORIGINAL_GET_RELOAD_PATHS
    from reflex_django.runtime.get_config_patch import (
        get_original_get_config,
        reset_get_config_patch_state,
    )

    original_get_config = get_original_get_config()
    if original_get_config is not None:
        import reflex_base.config as config_module

        config_module.get_config = original_get_config
        reset_get_config_patch_state()
    if _ORIGINAL_GET_RELOAD_PATHS is not None:
        try:
            import reflex.utils.exec as exec_module

            exec_module.get_reload_paths = _ORIGINAL_GET_RELOAD_PATHS
        except ImportError:
            pass
    try:
        import reflex_base.event.processor.base_state_processor as bsp

        original_pe = getattr(bsp, "_reflex_django_process_event_original", None)
        if original_pe is not None:
            bsp.process_event = original_pe
            bsp._reflex_django_process_event_patched = False
    except ImportError:
        pass
    try:
        from reflex_base.event.context import EventContext

        original_ed = getattr(EventContext, "_reflex_django_emit_delta_original", None)
        if original_ed is not None:
            EventContext.emit_delta = original_ed
            EventContext._reflex_django_emit_delta_patched = False
    except ImportError:
        pass
    from reflex_django.runtime.integration.patches.pages import _reflex_page_namespace

    page_module = _reflex_page_namespace()
    if page_module is not None:
        original_page = getattr(page_module, "_reflex_django_page_original", None)
        if original_page is not None:
            page_module.page = original_page
            page_module._reflex_django_page_patched = False
    try:
        from reflex.state import BaseState

        original_gs = getattr(BaseState, "_reflex_django_getstate_original", None)
        if original_gs is not None:
            BaseState.__getstate__ = original_gs  # type: ignore[method-assign]
            BaseState._reflex_django_getstate_patched = False
    except ImportError:
        pass
    set_installed(False)
    _ORIGINAL_GET_RELOAD_PATHS = None
