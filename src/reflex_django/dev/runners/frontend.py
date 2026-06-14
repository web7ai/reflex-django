"""Internal entry point that compiles and runs the Vite dev server.

``manage.py run_reflex`` spawns this module as a subprocess when it needs to
launch the Vite dev server in :class:`~reflex_django.setup.routing.UrlRoutingMode.DJANGO_OUTER`
mode. A fresh Python interpreter does not run reflex-django's import hooks
automatically — without ``install_reflex_django_integration()`` the Reflex
CLI fails with ``rxconfig.py not found`` (because our
:func:`~reflex_django.cli.layout.ensure_reflex_cli_layout` patch is not
installed).

We deliberately do not call ``reflex run --frontend-only`` here: Reflex's
``run`` command sets ``backend_port = backend_port or config.backend_port``
and then rejects the implicit value as ``Cannot specify --backend-port when
not running backend``. Instead we install the integration, compile the app,
and invoke ``reflex.utils.exec.run_frontend`` directly — same effect, no
spurious CLI validation.

Invoke as:

.. code-block:: bash

    python -m reflex_django.dev.runners.frontend --frontend-port 3000
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _RunnerArgs:
    """Parsed CLI options for the frontend runner."""

    frontend_port: int
    compile_only: bool
    compile_and_build: bool
    watch: bool
    skip_compile: bool


def _parse_argv(argv: list[str]) -> _RunnerArgs:
    parser = argparse.ArgumentParser(prog="reflex_django.dev.runners.frontend")
    parser.add_argument(
        "--frontend-port",
        dest="frontend_port",
        type=int,
        default=None,
        help="Port the Vite dev server should listen on.",
    )
    parser.add_argument(
        "--frontend-host",
        dest="frontend_host",
        default="127.0.0.1",
        help="Bind host for the Vite dev server.",
    )
    parser.add_argument(
        "--compile-only",
        dest="compile_only",
        action="store_true",
        help=(
            "Bootstrap reflex-django, compile the SPA into `.web`, then exit "
            "without starting Vite. Used by the watch loop to recompile in a "
            "fresh interpreter so edited modules are picked up."
        ),
    )
    parser.add_argument(
        "--compile-and-build",
        dest="compile_and_build",
        action="store_true",
        help=(
            "Compile the SPA into `.web`, run Reflex's Python frontend build "
            "(``setup_frontend`` + ``build.build``), then exit. Used by "
            "compile-dev watch to refresh the disk bundle after Reflex edits."
        ),
    )
    parser.add_argument(
        "--skip-compile",
        dest="skip_compile",
        action="store_true",
        help=(
            "Skip the initial compile step. Used when ``manage.py run_reflex`` "
            "already compiled in the parent process (native Reflex layout)."
        ),
    )
    parser.add_argument(
        "--no-watch",
        dest="watch",
        action="store_false",
        help=(
            "Do not watch the Reflex source tree for changes. Compile once "
            "and run Vite with no recompile-on-change loop."
        ),
    )
    parser.set_defaults(watch=True)
    # Tolerate extra args so callers can pass through unrelated options.
    args, _extras = parser.parse_known_args(argv)

    port = args.frontend_port
    if port is None:
        env_port = os.environ.get("RX_FRONTEND_PORT")
        port = int(env_port) if env_port and env_port.isdigit() else 3000
    return _RunnerArgs(
        frontend_port=int(port),
        compile_only=bool(args.compile_only),
        compile_and_build=bool(args.compile_and_build),
        watch=bool(args.watch),
        skip_compile=bool(args.skip_compile),
    )


def _bootstrap_integration() -> None:
    from reflex_django.setup.conf import configure_django
    from reflex_django.runtime.integration import install_reflex_django_integration

    install_reflex_django_integration()
    try:
        from reflex_base.config import get_config

        get_config()
    except Exception:
        pass
    configure_django()


def _sync_vite_proxy_layout_after_compile() -> None:
    """Strip or apply Vite→Django proxies to match the active dev port layout."""
    try:
        from reflex_django.dev.vite_proxy import finalize_web_dev_layout

        finalize_web_dev_layout(force=True)
    except Exception as exc:  # noqa: BLE001
        print(
            f"reflex-django: could not sync Vite proxy layout ({exc!r}).",
            file=sys.stderr,
        )


def _compile_app_for_frontend() -> None:
    """Run Reflex's compile step so ``.web`` is up to date before Vite starts."""
    from reflex.utils import prerequisites

    prerequisites.compile_or_validate_app(
        True,
        check_if_schema_up_to_date=True,
        prerender_routes=False,
    )
    _write_env_json()
    _sync_vite_proxy_layout_after_compile()


def _write_env_json() -> None:
    """Write ``.web/env.json`` so Vite can resolve ``$/env.json`` imports.

    Reflex's generated ``.web/utils/state.js`` imports ``$/env.json`` (the
    endpoint URL map). ``reflex run`` produces it via
    :func:`reflex.utils.build.setup_frontend`; because we drive Vite ourselves
    we must write it too, otherwise Vite fails with
    ``Cannot find module '$/env.json'``. The call is idempotent, so running it
    on every compile (startup and each recompile) keeps the file present and
    in sync with the active config.
    """
    try:
        from reflex.utils import build

        build.set_env_json()
    except Exception as exc:  # noqa: BLE001
        print(
            f"reflex-django: could not write .web/env.json ({exc!r}). "
            "Vite may fail to resolve `$/env.json`.",
            file=sys.stderr,
        )


def _apply_persistent_frontend_port(port: int) -> None:
    """Push ``frontend_port`` into the active :class:`rx.Config` (mirrors reflex run)."""
    try:
        from reflex_base.config import get_config
    except Exception:
        return
    try:
        cfg = get_config()
        if hasattr(cfg, "_set_persistent"):
            cfg._set_persistent(frontend_port=port)
        elif hasattr(cfg, "frontend_port"):
            cfg.frontend_port = port
    except Exception:
        pass


def _run_vite(port: int) -> int:
    from reflex.utils import exec as reflex_exec

    root = Path.cwd()
    os.environ["PORT"] = str(port)
    reflex_exec.run_frontend(root, str(port), backend_present=False)
    return 0


def _resolve_watch_paths() -> list[Path]:
    """Return the source paths to watch for recompilation.

    We watch the **Django project root** (``settings.BASE_DIR``, falling back
    to the current working directory) so that editing any Reflex page/state
    ``.py`` anywhere in the project is detected. Reflex's own
    :func:`reflex.utils.exec.get_reload_paths` resolves paths from the Reflex
    ``config.module`` layout, which does not always line up with a
    Django-first project tree, so it would silently watch the wrong directory
    and "save does nothing" would result.

    Only ``.py`` changes trigger a recompile (see the ``PythonFilter`` in
    :func:`_start_watch_thread`), so watching the project root does not loop on
    the ``.web`` (``.js``) output that the recompile itself writes.
    """
    from reflex_django.dev.watch import resolve_dev_watch_roots

    return resolve_dev_watch_roots()


def _recompile_in_subprocess(port: int, *, compile_and_build: bool = False) -> None:
    """Recompile the SPA in a fresh interpreter so edited modules are reloaded.

    Recompiling in-process would re-use the already-imported (stale) Reflex
    page/state modules, so the regenerated ``.web`` would not reflect the
    edit. Spawning ``python -m reflex_django.dev.runners.frontend --compile-only``
    gives us a clean import every time; Vite (still running in this process)
    then hot-reloads from the freshly written ``.web`` output.

    When ``compile_and_build`` is True, the subprocess also runs Reflex's
    Python frontend build so the disk bundle under ``.web/build/client`` updates.
    """
    cmd = [
        sys.executable,
        "-m",
        "reflex_django.dev.runners.frontend",
    ]
    if compile_and_build:
        cmd.append("--compile-and-build")
    else:
        cmd.extend(["--frontend-port", str(port), "--compile-only"])
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(
            "reflex-django: recompile failed; keeping the previous `.web` "
            "bundle. Fix the error above and save again.",
            file=sys.stderr,
        )
    elif compile_and_build:
        print(
            "reflex-django: recompiled and rebuilt `.web/build/client` "
            "(browser will auto-reload)."
        )
    elif str(os.environ.get("RX_COMPILE_DEV", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        print(
            "reflex-django: recompiled `.web` (compile-only, no JS build)."
        )
    else:
        print("reflex-django: recompiled `.web` - Vite hot-reloading frontend.")


def _start_watch_thread(port: int) -> threading.Thread | None:
    """Start a daemon thread that recompiles ``.web`` on Reflex source changes.

    Returns the thread (already started) or ``None`` if ``watchfiles`` is not
    installed, in which case the caller proceeds without a recompile loop.
    """
    try:
        from watchfiles import PythonFilter, watch

        from reflex_django.dev.watch import (
            WATCH_DEBOUNCE_MS,
            build_frontend_watch_filter,
        )
    except Exception:  # noqa: BLE001
        print(
            "reflex-django: `watchfiles` is not installed — frontend "
            "hot-reload-on-edit is disabled. Install `uvicorn[standard]` (or "
            "`watchfiles`) to recompile the SPA automatically on save.",
            file=sys.stderr,
        )
        return None

    watch_paths = [str(p) for p in _resolve_watch_paths()]
    watch_filter = build_frontend_watch_filter(PythonFilter)

    def _loop() -> None:
        try:
            for changes in watch(
                *watch_paths,
                watch_filter=watch_filter,
                debounce=WATCH_DEBOUNCE_MS,
                step=50,
                yield_on_timeout=False,
                raise_interrupt=False,
            ):
                if not changes:
                    continue
                _recompile_in_subprocess(port)
        except Exception as exc:  # noqa: BLE001
            print(
                f"reflex-django: frontend watch loop stopped ({exc!r}). "
                "Restart `run_reflex` to resume hot-reload.",
                file=sys.stderr,
            )

    thread = threading.Thread(
        target=_loop, name="reflex-django-frontend-watch", daemon=True
    )
    thread.start()
    print(
        "reflex-django: watching "
        f"{', '.join(watch_paths)} for Reflex edits (frontend HMR)."
    )
    return thread


def _compile_once_safe() -> None:
    """Compile the SPA, downgrading failures to a warning."""
    try:
        _compile_app_for_frontend()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(
            f"reflex-django: frontend compile failed ({exc!r}). "
            "Vite will still start but pages may be missing.",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    """Bootstrap reflex-django, compile, and run Vite directly.

    In the default mode this also starts a watch loop that recompiles the SPA
    on Reflex source edits so Vite hot-reloads the frontend without restarting
    the backend. ``--compile-only`` performs a single compile and exits (used
    internally by the watch loop); ``--no-watch`` runs Vite without the loop.
    """
    parsed = list(argv if argv is not None else sys.argv[1:])
    args = _parse_argv(parsed)

    _bootstrap_integration()
    _apply_persistent_frontend_port(args.frontend_port)

    if args.compile_and_build:
        build_frontend_disk_bundle(compile_first=True)
        return 0

    if args.compile_only:
        # Re-raise SystemExit so a non-zero exit propagates to the watch loop.
        _compile_app_for_frontend()
        return 0

    if args.skip_compile:
        _write_env_json()
    else:
        _compile_once_safe()

    if args.watch:
        _start_watch_thread(args.frontend_port)

    try:
        return _run_vite(args.frontend_port)
    except KeyboardInterrupt:
        return 0


BUILD_ID_PATH = "/__reflex_django/dev/build-id"
COMPILE_DEV_CLIENT_BACKUP_DIRNAME = ".compile-dev-client-backup"


def compile_dev_client_backup_dir() -> Path:
    """Return the directory that holds the previous client bundle during rebuilds."""
    from reflex.utils.prerequisites import get_web_dir

    return get_web_dir() / COMPILE_DEV_CLIENT_BACKUP_DIRNAME


def _backup_client_bundle_before_build() -> None:
    """Copy the current client bundle aside before Reflex wipes ``.web/build``."""
    import shutil

    from reflex.utils import path_ops
    from reflex.utils.prerequisites import get_web_dir
    from reflex_base import constants as reflex_constants

    wdir = get_web_dir()
    static_dir = wdir / reflex_constants.Dirs.STATIC
    if not (static_dir / "index.html").is_file():
        return
    backup = compile_dev_client_backup_dir()
    path_ops.rm(str(backup))
    shutil.copytree(static_dir, backup)


def _clear_compile_dev_client_backup() -> None:
    """Remove the compile-dev backup after a successful frontend build."""
    from reflex.utils import path_ops

    backup = compile_dev_client_backup_dir()
    if backup.is_dir():
        path_ops.rm(str(backup))


def build_id_for_disk_bundle() -> str:
    """Return a token that changes whenever the SPA or compile output updates."""
    try:
        from reflex_django.mount.spa_paths import resolve_spa_index

        index = resolve_spa_index()
    except Exception:  # noqa: BLE001
        index = None
    if index is not None:
        try:
            stat = index.stat()
            return f"bundle:{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            pass
    try:
        from reflex.utils.prerequisites import get_web_dir

        env_json = get_web_dir() / "env.json"
        if env_json.is_file():
            stat = env_json.stat()
            return f"compile:{stat.st_mtime_ns}:{stat.st_size}"
    except Exception:  # noqa: BLE001
        pass
    return "missing"


def _ensure_dev_env_mode() -> None:
    from reflex_base import constants as reflex_constants
    from reflex_base.environment import environment

    environment.REFLEX_ENV_MODE.set(reflex_constants.Env.DEV)


def _finalize_reflex_client_build(*, compress: bool = False) -> None:
    """Mirror ``reflex.utils.build.build`` post-processing without the JS subprocess."""
    from pathlib import PosixPath

    from reflex.utils import build as reflex_build
    from reflex.utils import path_ops
    from reflex.utils.prerequisites import get_web_dir
    from reflex_base import constants as reflex_constants
    from reflex_base.config import get_config

    wdir = get_web_dir()
    static_dir = wdir / reflex_constants.Dirs.STATIC
    config = get_config()

    reflex_build._duplicate_index_html_to_parent_directory(static_dir)

    for plugin in config.plugins:
        plugin.post_build(static_dir=static_dir)

    spa_fallback = static_dir / reflex_constants.ReactRouter.SPA_FALLBACK
    if not spa_fallback.exists():
        spa_fallback = static_dir / "index.html"
    if spa_fallback.exists():
        path_ops.cp(spa_fallback, static_dir / "404.html")

    if compress:
        reflex_build._compress_static_output(
            static_dir,
            tuple(config.frontend_compression_formats),
        )

    if frontend_path := config.frontend_path.strip("/"):
        frontend_path = PosixPath(frontend_path)
        first_part = frontend_path.parts[0]
        for child in list(static_dir.iterdir()):
            if child.is_dir() and child.name == first_part:
                continue
            path_ops.mv(
                child,
                static_dir / frontend_path / child.name,
            )


def _run_compile_dev_frontend_export() -> None:
    """Run Reflex's ``run export`` step without ``build.build()``'s production UI."""
    from reflex.utils import js_runtimes, path_ops, prerequisites
    from reflex_base import constants as reflex_constants

    wdir = prerequisites.get_web_dir()
    path_ops.rm(str(wdir / reflex_constants.Dirs.BUILD_DIR))
    js_runtimes.validate_frontend_dependencies(init=False)
    cmd = [
        *js_runtimes.get_js_package_executor(raise_on_none=True)[0],
        "run",
        "export",
    ]
    env = {**os.environ, "NO_COLOR": "1"}
    print(
        "reflex-django: building frontend bundle (compile-dev)...",
        flush=True,
    )
    result = subprocess.run(
        cmd,
        cwd=wdir,
        env=env,
        check=False,
        shell=reflex_constants.IS_WINDOWS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Reflex frontend export failed with exit code "
            f"{result.returncode}."
        )


def build_frontend_client_bundle() -> None:
    """Build the servable client bundle for compile-dev mode.

    Uses the same ``run export`` subprocess as ``reflex.utils.build.build``,
    but skips Reflex's hard-coded "Creating Production Build" progress bar
    (that label is used even when ``REFLEX_ENV_MODE=dev``).
    """
    from reflex.utils import build as reflex_build
    from reflex.utils.prerequisites import get_web_dir
    from reflex_base import constants as reflex_constants

    _ensure_dev_env_mode()
    _backup_client_bundle_before_build()
    reflex_build.setup_frontend(Path.cwd())
    try:
        _run_compile_dev_frontend_export()
        _finalize_reflex_client_build(compress=False)
    except RuntimeError:
        raise
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise RuntimeError(
            f"Reflex frontend build failed (exit {code})."
        ) from exc
    static_dir = get_web_dir() / reflex_constants.Dirs.STATIC
    if (static_dir / "index.html").is_file():
        _clear_compile_dev_client_backup()


def build_frontend_disk_bundle(*, compile_first: bool = True) -> None:
    """Compile the Reflex app, then build the servable client bundle via Reflex."""
    if compile_first:
        _compile_app_for_frontend()
    build_frontend_client_bundle()


def run_client_build() -> None:
    """Backward-compatible alias for :func:`build_frontend_client_bundle`."""
    build_frontend_client_bundle()


def run_vite_client_build(*, watch: bool = False) -> subprocess.Popen[bytes] | None:
    """Backward-compatible alias for :func:`build_frontend_client_bundle`."""
    if watch:
        raise RuntimeError(
            "compile-dev watch rebuilds via --compile-and-build, not a watch subprocess."
        )
    build_frontend_client_bundle()
    return None


def start_compile_dev_watch() -> threading.Thread | None:
    """Watch ``.py`` files and recompile ``.web/`` (no ``react-router build``)."""
    try:
        from watchfiles import PythonFilter, watch

        from reflex_django.dev.watch import (
            WATCH_DEBOUNCE_MS,
            build_frontend_watch_filter,
        )
    except Exception:  # noqa: BLE001
        print(
            "reflex-django: `watchfiles` is not installed — compile dev watch disabled.",
            file=sys.stderr,
        )
        return None

    watch_paths = [str(p) for p in _resolve_watch_paths()]
    watch_filter = build_frontend_watch_filter(PythonFilter)

    def _loop() -> None:
        try:
            for changes in watch(
                *watch_paths,
                watch_filter=watch_filter,
                debounce=WATCH_DEBOUNCE_MS,
                step=50,
                yield_on_timeout=False,
                raise_interrupt=False,
            ):
                if changes:
                    _recompile_in_subprocess(0, compile_and_build=False)
        except Exception as exc:  # noqa: BLE001
            print(
                f"reflex-django: compile dev watch stopped ({exc!r}).",
                file=sys.stderr,
            )

    thread = threading.Thread(
        target=_loop,
        name="reflex-django-compile-dev-watch",
        daemon=True,
    )
    thread.start()
    print(
        "reflex-django: watching "
        f"{', '.join(watch_paths)} for Reflex edits (recompile `.web/` only)."
    )
    return thread


if __name__ == "__main__":
    sys.exit(main())
