"""Patch registry: install/uninstall and original callables."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from reflex_base.config import Config

from reflex_django.setup.project import RXCONFIG_SYNTHETIC_ATTR, discover_settings_module

_INSTALLED = False
_ORIGINAL_GET_CONFIG: Callable[..., Config] | None = None
_ORIGINAL_GET_RELOAD_PATHS: Callable[[], Any] | None = None
_ORIGINAL_CHECK_APP_NAME: Callable[..., Any] | None = None
_ORIGINAL_GET_APP_FILE: Callable[[], Any] | None = None
_ORIGINAL_COMPILE_OR_VALIDATE: Callable[..., bool] | None = None


def is_installed() -> bool:
    return _INSTALLED


def set_installed(value: bool) -> None:
    global _INSTALLED
    _INSTALLED = value


def get_original_get_config() -> Callable[..., Config] | None:
    return _ORIGINAL_GET_CONFIG


def get_original_compile_or_validate() -> Callable[..., bool] | None:
    return _ORIGINAL_COMPILE_OR_VALIDATE


def set_original_compile_or_validate(fn: Callable[..., bool] | None) -> None:
    global _ORIGINAL_COMPILE_OR_VALIDATE
    _ORIGINAL_COMPILE_OR_VALIDATE = fn


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
        from reflex_django.setup.rxconfig_bridge import build_merged_config_for_django_mode

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



def refresh_get_config_bindings() -> None:
    """Rebind `get_config` on Reflex modules loaded after the initial patch."""
    import reflex_base.config as config_module

    patched = config_module.get_config
    if patched is get_original_get_config():
        return
    _rebind_get_config_imports(patched)

def _patch_reload_paths() -> None:
    """Watch Django ``BASE_DIR`` instead of reflex-django's runtime module path."""
    global _ORIGINAL_GET_RELOAD_PATHS
    try:
        import reflex.utils.exec as exec_module
    except ImportError:
        return

    if _ORIGINAL_GET_RELOAD_PATHS is not None:
        return

    _ORIGINAL_GET_RELOAD_PATHS = exec_module.get_reload_paths

    def patched_get_reload_paths() -> Any:
        from reflex_django.dev.watch import django_first_reload_paths

        return django_first_reload_paths()

    exec_module.get_reload_paths = patched_get_reload_paths  # type: ignore[assignment]


def _patch_prerequisites_app_module() -> None:
    """Ensure Django-first ``{app_name}/{app_name}.py`` exists before Reflex validates it."""
    global _ORIGINAL_CHECK_APP_NAME, _ORIGINAL_GET_APP_FILE
    try:
        import reflex.utils.exec as exec_module
        import reflex.utils.prerequisites as prerequisites
    except ImportError:
        return

    if _ORIGINAL_CHECK_APP_NAME is not None:
        return

    _ORIGINAL_CHECK_APP_NAME = prerequisites._check_app_name
    _ORIGINAL_GET_APP_FILE = exec_module.get_app_file

    def patched_check_app_name(config: Config) -> None:
        from reflex_django.mount.config import resolve_app_name
        from reflex_django.runtime.app_factory import (
            ensure_reflex_app_module_stub,
            reflex_app_module_name,
        )

        if config.module == reflex_app_module_name(resolve_app_name()):
            ensure_reflex_app_module_stub()
        return _ORIGINAL_CHECK_APP_NAME(config)

    def patched_get_app_file() -> Any:
        from reflex_base.config import get_config

        from reflex_django.mount.config import resolve_app_name
        from reflex_django.runtime.app_factory import (
            ensure_reflex_app_module_stub,
            reflex_app_module_name,
        )

        config = get_config()
        if config.module == reflex_app_module_name(resolve_app_name()):
            stub = ensure_reflex_app_module_stub()
            if stub is not None and stub.is_file():
                return stub
        return _ORIGINAL_GET_APP_FILE()

    prerequisites._check_app_name = patched_check_app_name  # type: ignore[assignment]
    exec_module.get_app_file = patched_get_app_file  # type: ignore[assignment]


def _patch_vite_dev_dependency() -> None:
    """Opt-in override for the ``vite`` devDependency Reflex pins.

    Reflex pins a specific Vite version in
    ``reflex_base.constants.installer.PackageJson.DEV_DEPENDENCIES`` and
    regenerates ``.web/package.json`` from it on every compile. Some Vite
    releases ship known frontend regressions (e.g. the Rolldown CJS-interop
    bug in Vite 8.0.x that emits ``var r=r(), t=t(), n=n(), i=i();`` and
    crashes ``recharts`` and Reflex's Socket.IO dispatcher with
    ``TypeError: <var> is not a function``). When that happens you can pin a
    known-good Vite without forking ``reflex-django``:

    - Set ``RX_VITE_VERSION = "7.3.3"`` in your Django settings, or
    - Export ``RX_VITE_VERSION=7.3.3`` in your shell environment.

    The setting takes priority over the env var. When neither is set (the
    default), :mod:`reflex_django` makes **no change** to the Vite version —
    you get whatever the installed ``reflex_base`` package ships with.
    """
    desired: str | None = None

    try:
        from django.conf import settings as django_settings

        candidate = getattr(django_settings, "RX_VITE_VERSION", None)
        if isinstance(candidate, str) and candidate.strip():
            desired = candidate.strip()
    except Exception:  # noqa: BLE001 — Django may not be configured yet.
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
    "        if (typeof _rxdj_dispatch !== \"function\") {\n"
    "          if (typeof console !== \"undefined\" && console.warn) {\n"
    "            console.warn(\n"
    "              \"[reflex-django] No dispatcher for substate '\" + substate + \"' — \"\n"
    "              + \"skipping delta. This usually means the Python state tree \"\n"
    "              + \"changed since the SPA was built; re-run `python manage.py \"\n"
    "              + \"export_reflex` to regenerate. Known dispatchers: \"\n"
    "              + Object.keys(dispatch).join(\", \"),\n"
    "            );\n"
    "          }\n"
    "          continue;\n"
    "        }\n"
    "        _rxdj_dispatch(update.delta[substate]);"
)


def _patch_state_dispatcher_template() -> None:
    """Make the generated ``utils/state.js`` tolerant of unknown substates.

    The stock Reflex template calls ``dispatch[substate](delta)`` without
    checking that the substate exists in the client-side dispatcher map.
    When the running backend's state tree drifts from the bundle (typically
    because ``.web/`` was generated against an older set of imports than the
    process is now serving, or a substate is registered late), the WebSocket
    event handler throws ``TypeError: h[M] is not a function`` and the page
    sits forever on the loading skeleton.

    We patch the bundled template at boot so every subsequent compile emits a
    guarded dispatch that logs the missing substate to the browser console
    instead of crashing the page. The patch is idempotent and recoverable:
    reinstalling ``reflex_base`` overwrites the template and the next process
    boot re-applies the patch.
    """
    from pathlib import Path  # noqa: PLC0415 — keep import local to the patch.

    template_path: Path | None = None
    try:
        import reflex_base  # noqa: PLC0415

        template_path = (
            Path(reflex_base.__file__).parent
            / ".templates"
            / "web"
            / "utils"
            / "state.js"
        )
    except Exception:  # noqa: BLE001 — best-effort discovery.
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
        import logging

        logging.getLogger("reflex_django.runtime.integration.registry").warning(
            "Could not patch %s for tolerant dispatcher; readonly site-packages?",
            template_path,
        )


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
        from reflex_django.cli.layout import ensure_reflex_cli_layout

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
        from reflex_django.cli.layout import ensure_reflex_cli_layout

        ensure_reflex_cli_layout()
        return False

    prerequisites.needs_reinit = patched_needs_reinit
    prerequisites._reflex_django_needs_reinit_patched = True
    prerequisites._reflex_django_needs_reinit_original = original




def install_bootstrap_patches() -> None:
    """Apply early patches before ``rxconfig`` is materialized."""
    _patch_get_config()
    _patch_reload_paths()
    _patch_prerequisites_app_module()
    _patch_vite_dev_dependency()
    _patch_state_dispatcher_template()


def install_post_rxconfig_patches() -> None:
    """Apply compile and page patches after ``rxconfig`` is available."""
    from reflex_django.runtime.integration.patches.compile import (
        _patch_app_compile,
        _patch_compile_or_validate_app,
        _patch_reflex_compile,
        _patch_vite_config_generation,
    )
    from reflex_django.runtime.integration.patches.pages import (
        _patch_apply_decorated_pages,
        _patch_reflex_page,
    )

    _patch_vite_config_generation()
    _patch_app_compile()
    _patch_compile_or_validate_app()
    _patch_reflex_compile()
    _patch_reflex_page()
    _patch_apply_decorated_pages()
    _patch_assert_in_reflex_dir()
    _patch_needs_reinit()


def uninstall_all_patches() -> None:
    """Restore unpatched Reflex hooks."""
    global _ORIGINAL_GET_CONFIG, _ORIGINAL_GET_RELOAD_PATHS
    global _ORIGINAL_CHECK_APP_NAME, _ORIGINAL_GET_APP_FILE
    global _ORIGINAL_COMPILE_OR_VALIDATE
    if _ORIGINAL_GET_CONFIG is not None:
        import reflex_base.config as config_module

        config_module.get_config = _ORIGINAL_GET_CONFIG
    if _ORIGINAL_GET_RELOAD_PATHS is not None:
        try:
            import reflex.utils.exec as exec_module

            exec_module.get_reload_paths = _ORIGINAL_GET_RELOAD_PATHS
        except ImportError:
            pass
    if _ORIGINAL_CHECK_APP_NAME is not None:
        try:
            import reflex.utils.exec as exec_module
            import reflex.utils.prerequisites as prerequisites

            prerequisites._check_app_name = _ORIGINAL_CHECK_APP_NAME
            if _ORIGINAL_GET_APP_FILE is not None:
                exec_module.get_app_file = _ORIGINAL_GET_APP_FILE
        except ImportError:
            pass
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
        if _ORIGINAL_COMPILE_OR_VALIDATE is not None:
            prerequisites.compile_or_validate_app = _ORIGINAL_COMPILE_OR_VALIDATE
            prerequisites._reflex_django_compile_or_validate_patched = False
    except ImportError:
        pass
    mod = sys.modules.get("rxconfig")
    if mod is not None and getattr(mod, RXCONFIG_SYNTHETIC_ATTR, False):
        sys.modules.pop("rxconfig", None)
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
    _ORIGINAL_GET_CONFIG = None
    _ORIGINAL_GET_RELOAD_PATHS = None
    _ORIGINAL_CHECK_APP_NAME = None
    _ORIGINAL_GET_APP_FILE = None
    _ORIGINAL_COMPILE_OR_VALIDATE = None
