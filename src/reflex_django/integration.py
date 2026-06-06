"""Django-first bootstrap: settings discovery and ``get_config`` patching."""

from __future__ import annotations

import contextlib
import importlib
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

# Per-event attributes bound on :class:`reflex.state.BaseState` instances by
# the Django-outer bridge that must NEVER reach :mod:`dill`/:mod:`pickle`.
# They hold a live :class:`~django.http.HttpRequest`/``HttpResponse``,
# a hydrated :class:`~django.contrib.auth.models.User`, and a
# :class:`~django.urls.ResolverMatch` — none of which are reliably picklable
# (the User pulls in ``Group_permissions`` through-tables; ``ResolverMatch``
# captures view callables/closures). The bridge re-attaches them on every
# event from context vars, so it is safe to drop them from serialization.
_DJANGO_TRANSIENT_STATE_ATTRS: tuple[str, ...] = (
    "_django_led_request_wrapper",
    "_django_led_response",
)


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


def _ensure_runtime_event_patches() -> None:
    """Apply hooks so ``self.request`` works on handler substates (idempotent)."""
    _patch_process_event()
    _patch_event_context_emit_delta()
    _patch_basestate_getstate()


_DJANGO_OUTER_ASGI_TARGET = "reflex_django.asgi_entry:application"
_BACKEND_RELOAD_ENV = "REFLEX_DJANGO_BACKEND_RELOAD"
_FRONTEND_PRESENT_ENV = "REFLEX_DJANGO_FRONTEND_PRESENT"


def _backend_reload_enabled() -> bool:
    """Return whether the patched Reflex dev backend should use uvicorn reload."""
    env = os.environ.get(_BACKEND_RELOAD_ENV)
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    return True


def _django_watch_root() -> str:
    """Return Django ``BASE_DIR`` for backend reload watching."""
    try:
        from django.conf import settings

        base = getattr(settings, "BASE_DIR", None)
        if base:
            return str(base)
    except Exception:  # noqa: BLE001
        pass
    return str(os.getcwd())


def _spawn_django_outer_backend_subprocess(
    host: str,
    port: int,
    loglevel: Any,
    *,
    reload: bool,
) -> None:
    """Run the Django-outer backend in a child interpreter (Windows-safe with Vite)."""
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "reflex_django._backend_runner",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        str(getattr(loglevel, "value", loglevel)),
    ]
    if not reload:
        cmd.append("--no-reload")

    install_reflex_django_integration()
    proc = subprocess.Popen(cmd, env={**os.environ})
    try:
        proc.wait()
    except KeyboardInterrupt:
        with contextlib.suppress(Exception):
            proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)
        with contextlib.suppress(Exception):
            proc.kill()


def _patch_reflex_run_backend() -> None:
    """Point ``reflex run`` at the Django-outer ASGI entry in ``DJANGO_OUTER`` mode."""
    if resolve_url_routing() != UrlRoutingMode.DJANGO_OUTER:
        return

    try:
        import reflex.utils.exec as exec_module
    except ImportError:
        return

    if getattr(exec_module, "_reflex_django_run_backend_patched", False):
        return

    from reflex_base.constants.base import LogLevel

    original_run_backend = exec_module.run_backend
    original_run_uvicorn = exec_module.run_uvicorn_backend
    original_run_granian = exec_module.run_granian_backend
    original_run_uvicorn_prod = exec_module.run_uvicorn_backend_prod
    original_run_granian_prod = exec_module.run_granian_backend_prod

    def _django_outer_run_uvicorn_backend(
        host: str, port: int, loglevel: LogLevel
    ) -> None:
        reload = _backend_reload_enabled()
        frontend_present = os.environ.get(_FRONTEND_PRESENT_ENV) == "1"

        # Reflex runs Vite concurrently on Windows while ``run_backend`` blocks
        # the main thread. In-process ``uvicorn.run(..., reload=True)`` in that
        # layout often never binds :8000; delegate to a child interpreter.
        if frontend_present or (reload and sys.platform == "win32"):
            _spawn_django_outer_backend_subprocess(
                host, port, loglevel, reload=reload
            )
            return

        import uvicorn

        from reflex.utils.exec import get_reload_paths

        from reflex_django.dev_watch import (
            BACKEND_RELOAD_DELAY_S,
            backend_reload_excludes,
        )

        run_kwargs: dict[str, Any] = {
            "app": _DJANGO_OUTER_ASGI_TARGET,
            "factory": False,
            "host": host,
            "port": port,
            "log_level": loglevel.value,
            "reload": reload,
            "ws": "auto",
        }
        if reload:
            watch_root = _django_watch_root()
            reflex_paths = list(map(str, get_reload_paths()))
            run_kwargs["reload_dirs"] = (
                [watch_root, *reflex_paths]
                if watch_root not in reflex_paths
                else reflex_paths or [watch_root]
            )
            run_kwargs["reload_delay"] = BACKEND_RELOAD_DELAY_S
        install_reflex_django_integration()
        uvicorn.run(**run_kwargs)

    def _django_outer_run_granian_backend(
        host: str, port: int, loglevel: LogLevel
    ) -> None:
        from granian.constants import Interfaces
        from granian.log import LogLevels
        from granian.server import Server as Granian
        from reflex.utils.exec import HOTRELOAD_IGNORE_PATTERNS, get_reload_paths
        from reflex_base.environment import _load_dotenv_from_env

        reload = _backend_reload_enabled()
        granian_kwargs: dict[str, Any] = {
            "target": _DJANGO_OUTER_ASGI_TARGET,
            "factory": False,
            "address": host,
            "port": port,
            "interface": Interfaces.ASGI,
            "log_level": LogLevels(loglevel.value),
            "reload": reload,
            "reload_ignore_worker_failure": True,
            "reload_ignore_patterns": HOTRELOAD_IGNORE_PATTERNS,
            "reload_tick": 100,
            "workers_kill_timeout": 2,
        }
        if reload:
            granian_kwargs["reload_paths"] = get_reload_paths()
        granian_app = Granian(**granian_kwargs)
        if reload:
            granian_app.on_reload(_load_dotenv_from_env)
        granian_app.serve()

    def _django_outer_run_backend(
        host: str,
        port: int,
        loglevel: Any = None,
        frontend_present: bool = False,
    ) -> None:
        from reflex.utils.exec import get_web_dir, notify_backend, should_use_granian

        if loglevel is None:
            from reflex_base.constants.base import LogLevel as LL

            loglevel = LL.ERROR

        web_dir = get_web_dir()
        if web_dir.exists():
            from reflex_base import constants

            (web_dir / constants.NOCOMPILE_FILE).touch()

        if frontend_present:
            os.environ[_FRONTEND_PRESENT_ENV] = "1"
        else:
            os.environ.pop(_FRONTEND_PRESENT_ENV, None)
            notify_backend(host)

        if should_use_granian():
            import reflex.app  # noqa: F401

            if frontend_present or (sys.platform == "win32" and _backend_reload_enabled()):
                _spawn_django_outer_backend_subprocess(
                    host, port, loglevel, reload=_backend_reload_enabled()
                )
            else:
                _django_outer_run_granian_backend(host, port, loglevel)
        else:
            _django_outer_run_uvicorn_backend(host, port, loglevel)

    def _django_outer_run_uvicorn_backend_prod(
        host: str,
        port: int,
        loglevel: LogLevel,
        app_target: str | None = None,
    ) -> None:
        original_run_uvicorn_prod(
            host,
            port,
            loglevel,
            app_target=app_target or _DJANGO_OUTER_ASGI_TARGET,
        )

    def _django_outer_run_granian_backend_prod(
        host: str,
        port: int,
        loglevel: LogLevel,
        app_target: str | None = None,
    ) -> None:
        original_run_granian_prod(
            host,
            port,
            loglevel,
            app_target=app_target or _DJANGO_OUTER_ASGI_TARGET,
        )

    exec_module.run_backend = _django_outer_run_backend
    exec_module.run_uvicorn_backend = _django_outer_run_uvicorn_backend
    exec_module.run_granian_backend = _django_outer_run_granian_backend
    exec_module.run_uvicorn_backend_prod = _django_outer_run_uvicorn_backend_prod
    exec_module.run_granian_backend_prod = _django_outer_run_granian_backend_prod
    exec_module._reflex_django_run_backend_patched = True


def install_reflex_django_integration() -> None:
    """Bootstrap reflex-django for the current process (idempotent)."""
    global _INSTALLED

    _ensure_settings_env()
    configure_django()
    _ensure_runtime_event_patches()
    _patch_reflex_run_backend()

    if _INSTALLED:
        _refresh_django_runtime()
        return

    _patch_get_config()
    _patch_vite_dev_dependency()
    _patch_state_dispatcher_template()

    from reflex_django.cli_layout import ensure_reflex_cli_layout
    from reflex_django.mount_config import ensure_mount_config_loaded
    from reflex_django.rxconfig_bridge import ensure_rxconfig_from_django

    ensure_mount_config_loaded()
    from reflex_django.auto_mount import maybe_auto_mount

    maybe_auto_mount()
    ensure_reflex_cli_layout()
    ensure_rxconfig_from_django()
    if resolve_url_routing() == UrlRoutingMode.DJANGO_LED:
        from reflex_django.app_factory import ensure_django_led_app_ready

        ensure_django_led_app_ready()

    _patch_reflex_compile()
    _patch_reflex_page()
    _patch_apply_decorated_pages()
    _patch_assert_in_reflex_dir()
    _patch_needs_reinit()
    _INSTALLED = True


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

    - Set ``REFLEX_DJANGO_VITE_VERSION = "7.3.3"`` in your Django settings, or
    - Export ``REFLEX_DJANGO_VITE_VERSION=7.3.3`` in your shell environment.

    The setting takes priority over the env var. When neither is set (the
    default), :mod:`reflex_django` makes **no change** to the Vite version —
    you get whatever the installed ``reflex_base`` package ships with.
    """
    desired: str | None = None

    try:
        from django.conf import settings as django_settings

        candidate = getattr(django_settings, "REFLEX_DJANGO_VITE_VERSION", None)
        if isinstance(candidate, str) and candidate.strip():
            desired = candidate.strip()
    except Exception:  # noqa: BLE001 — Django may not be configured yet.
        pass

    if desired is None:
        env_value = os.environ.get("REFLEX_DJANGO_VITE_VERSION", "").strip()
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

        logging.getLogger("reflex_django.integration").warning(
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


def _patch_apply_decorated_pages() -> None:
    """Apply decorated pages under the Django ``app_name`` from ``reflex_mount()``."""
    try:
        import reflex.app as reflex_app_module
    except ImportError:
        return

    if getattr(reflex_app_module.App, "_reflex_django_apply_pages_patched", False):
        return

    original = reflex_app_module.App._apply_decorated_pages

    def _apply_decorated_pages(self) -> None:  # noqa: ANN001
        from reflex_django.app_factory import prepare_pages_for_compile

        if getattr(self, "_reflex_django_decorated_pages_applied", False):
            return

        prepare_pages_for_compile()
        self._reflex_django_decorated_pages_applied = True  # type: ignore[attr-defined]

    reflex_app_module.App._apply_decorated_pages = _apply_decorated_pages
    reflex_app_module.App._reflex_django_apply_pages_patched = True
    reflex_app_module.App._reflex_django_apply_pages_original = original


def _patch_process_event() -> None:
    """Bind ``self.request`` on the handler substate before each event runs."""
    try:
        import reflex_base.event.processor.base_state_processor as bsp
    except ImportError:
        return

    if getattr(bsp, "_reflex_django_process_event_patched", False):
        return

    original = bsp.process_event

    async def process_event(handler, payload, state, root_state):  # noqa: ANN001
        from reflex_django.middleware import bind_django_request_for_handler_state

        await bind_django_request_for_handler_state(state)
        await original(handler, payload, state, root_state)

    bsp.process_event = process_event
    bsp._reflex_django_process_event_patched = True
    bsp._reflex_django_process_event_original = original


def _patch_basestate_getstate() -> None:
    """Strip non-picklable Django wrappers from state before Reflex pickles it.

    The Django-outer event bridge attaches per-request artefacts on each Reflex
    state instance via :mod:`reflex_django.state.request_binding`:

    - ``_django_led_request_wrapper`` — :class:`~reflex_django.state.request.DjangoStateRequest`
      holding the live :class:`~django.http.HttpRequest` (and an authenticated
      :class:`~django.contrib.auth.models.User`, the URL ``ResolverMatch``,
      Django messages, etc.).
    - ``_django_led_response`` — the :class:`~django.http.HttpResponse`
      produced by ``settings.MIDDLEWARE``.

    Reflex serializes state to Redis/in-memory between events using
    :mod:`dill`. The Django user, the resolver match (which captures view
    functions and url-patterns), and the response object are all
    non-picklable in the general case and surface as
    :class:`reflex.utils.exceptions.StateSerializationError`. The bridge
    re-attaches these on every event from context vars, so dropping them
    before pickling is safe.
    """
    try:
        from reflex.state import BaseState
    except ImportError:
        return

    if getattr(BaseState, "_reflex_django_getstate_patched", False):
        return

    original_getstate = BaseState.__getstate__

    def patched_getstate(self: Any) -> dict[str, Any]:
        state = original_getstate(self)
        if not isinstance(state, dict):
            return state
        for transient in _DJANGO_TRANSIENT_STATE_ATTRS:
            state.pop(transient, None)
        return state

    BaseState.__getstate__ = patched_getstate  # type: ignore[method-assign]
    BaseState._reflex_django_getstate_patched = True
    BaseState._reflex_django_getstate_original = original_getstate


def _patch_event_context_emit_delta() -> None:
    """Filter emitted deltas to substates present in ``.web/utils/context.js``."""
    try:
        from reflex_base.event.context import EventContext
    except ImportError:
        return

    if getattr(EventContext, "_reflex_django_emit_delta_patched", False):
        return

    original_emit_delta = EventContext.emit_delta

    async def emit_delta(
        self: Any,
        delta: Any,
    ) -> None:
        from reflex_django.compile_validate import filter_delta_to_compiled_dispatch_keys

        if not delta:
            return
        filtered = filter_delta_to_compiled_dispatch_keys(dict(delta))
        if not filtered:
            return
        await original_emit_delta(self, filtered)

    EventContext.emit_delta = emit_delta  # type: ignore[method-assign]
    EventContext._reflex_django_emit_delta_patched = True
    EventContext._reflex_django_emit_delta_original = original_emit_delta


def _reflex_page_namespace() -> Any | None:
    """Return :class:`reflex.page.PageNamespace` (not the lazy ``rx.page`` function)."""
    try:
        return importlib.import_module("reflex.page")
    except ImportError:
        return None


def _patch_reflex_page() -> None:
    """Bucket ``@page`` / ``@template`` under the mount ``app_name``, not ``""``."""
    page_module = _reflex_page_namespace()
    if page_module is None:
        return

    if getattr(page_module, "_reflex_django_page_patched", False):
        return

    original_page = page_module.page

    def patched_page(*args: Any, **kwargs: Any) -> Any:
        def decorator(render_fn: Any) -> Any:
            from reflex_base.config import get_config

            page_kwargs: dict[str, Any] = {}
            if args:
                page_kwargs["route"] = args[0]
            page_kwargs.update(kwargs)
            if "route" in page_kwargs and page_kwargs["route"] is None:
                page_kwargs.pop("route", None)

            bucket = _resolve_decorated_pages_app_name()
            page_module.DECORATED_PAGES[bucket].append((render_fn, page_kwargs))
            return render_fn

        return decorator

    page_module.page = patched_page  # type: ignore[assignment]
    page_module._reflex_django_page_patched = True
    page_module._reflex_django_page_original = original_page


def _resolve_decorated_pages_app_name() -> str:
    """Return the ``DECORATED_PAGES`` key for Django-first page registration."""
    from reflex_base.config import get_config

    try:
        from reflex_django.mount_config import has_mount_rx_config, resolve_app_name

        if has_mount_rx_config():
            return resolve_app_name()
    except ImportError:
        pass
    return str(get_config().app_name or "")


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
        from reflex_django.app_factory import load_app_factory, prepare_pages_for_compile
        from reflex_django.compile_validate import (
            expected_dispatch_keys_from_app,
            invalidate_stale_context_js,
            missing_frontend_dispatchers,
            warn_if_frontend_dispatchers_out_of_sync,
        )
        from reflex_django.frontend_stability import apply_frontend_stability_after_compile
        from reflex_django.vite_proxy import ensure_vite_django_dev_proxy_from_config

        prepare_pages_for_compile()
        app = load_app_factory()
        expected = expected_dispatch_keys_from_app(app)
        if missing_frontend_dispatchers(expected_keys=expected, app=app):
            invalidate_stale_context_js()
            if hasattr(app, "_reflex_django_decorated_pages_applied"):
                delattr(app, "_reflex_django_decorated_pages_applied")
            prepare_pages_for_compile()
            expected = expected_dispatch_keys_from_app(app)
        original_compile(avoid_dirty_check=False)
        apply_frontend_stability_after_compile()
        ensure_vite_django_dev_proxy_from_config()
        missing = missing_frontend_dispatchers(expected_keys=expected, app=app)
        if missing:
            invalidate_stale_context_js()
            if hasattr(app, "_reflex_django_decorated_pages_applied"):
                delattr(app, "_reflex_django_decorated_pages_applied")
            prepare_pages_for_compile()
            expected = expected_dispatch_keys_from_app(app)
            original_compile(avoid_dirty_check=False)
            apply_frontend_stability_after_compile()
            ensure_vite_django_dev_proxy_from_config()
            missing = missing_frontend_dispatchers(expected_keys=expected, app=app)
        warn_if_frontend_dispatchers_out_of_sync(expected_keys=expected, app=app)
        return None

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
    _INSTALLED = False
    _ORIGINAL_GET_CONFIG = None
