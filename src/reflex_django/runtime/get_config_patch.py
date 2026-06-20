"""Early ``get_config`` patch for the Reflex CLI ``.pth`` hook.

Kept separate from :mod:`reflex_django.runtime.integration` so site initialization
does not import Django or the full integration package before ``reflex_base`` is
available.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

_ORIGINAL_GET_CONFIG: Callable[..., Any] | None = None


def install_plugin_get_config_patch() -> None:
    """Wrap Reflex ``get_config`` to bootstrap plugin integration on first load."""
    global _ORIGINAL_GET_CONFIG
    import reflex_base.config as config_module

    if _ORIGINAL_GET_CONFIG is not None:
        return
    _ORIGINAL_GET_CONFIG = config_module.get_config

    def patched_get_config(reload: bool = False) -> Any:
        if reload:
            sys.modules.pop("rxconfig", None)
        original = _ORIGINAL_GET_CONFIG
        if original is None:
            from reflex_base.config import get_config

            return get_config(reload=reload)
        config = original(reload=reload)

        from reflex_django.runtime.integration.registry import is_installed

        if not is_installed():
            from reflex_django.runtime.integration.detect import (
                detect_reflex_django_plugin,
            )
            from reflex_django.runtime.integration import install_plugin_integration
            from reflex_django.runtime.integration.registry import set_installed

            plugin = detect_reflex_django_plugin(config)
            if plugin is not None:
                install_plugin_integration(plugin)
            else:
                set_installed(True)

        return config

    config_module.get_config = patched_get_config  # type: ignore[method-assign]
    _rebind_get_config_imports(patched_get_config)


def _rebind_get_config_imports(patched_get_config: Callable[..., Any]) -> None:
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


def get_original_get_config() -> Callable[..., Any] | None:
    return _ORIGINAL_GET_CONFIG


def reset_get_config_patch_state() -> None:
    global _ORIGINAL_GET_CONFIG
    _ORIGINAL_GET_CONFIG = None
