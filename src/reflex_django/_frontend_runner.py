"""Internal entry point that compiles and runs the Vite dev server.

``manage.py run_reflex`` spawns this module as a subprocess when it needs to
launch the Vite dev server in :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER`
mode. A fresh Python interpreter does not run reflex-django's import hooks
automatically — without ``install_reflex_django_integration()`` the Reflex
CLI fails with ``rxconfig.py not found`` (because our
:func:`~reflex_django.cli_layout.ensure_reflex_cli_layout` patch is not
installed).

We deliberately do not call ``reflex run --frontend-only`` here: Reflex's
``run`` command sets ``backend_port = backend_port or config.backend_port``
and then rejects the implicit value as ``Cannot specify --backend-port when
not running backend``. Instead we install the integration, compile the app,
and invoke ``reflex.utils.exec.run_frontend`` directly — same effect, no
spurious CLI validation.

Invoke as:

.. code-block:: bash

    python -m reflex_django._frontend_runner --frontend-port 3000
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
    watch: bool


def _parse_argv(argv: list[str]) -> _RunnerArgs:
    parser = argparse.ArgumentParser(prog="reflex_django._frontend_runner")
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
        env_port = os.environ.get("REFLEX_DJANGO_FRONTEND_PORT")
        port = int(env_port) if env_port and env_port.isdigit() else 3000
    return _RunnerArgs(
        frontend_port=int(port),
        compile_only=bool(args.compile_only),
        watch=bool(args.watch),
    )


def _bootstrap_integration() -> None:
    from reflex_django.conf import configure_django
    from reflex_django.integration import install_reflex_django_integration

    install_reflex_django_integration()
    try:
        from reflex_base.config import get_config

        get_config()
    except Exception:
        pass
    configure_django()


def _compile_app_for_frontend() -> None:
    """Run Reflex's compile step so ``.web`` is up to date before Vite starts."""
    from reflex.utils import prerequisites

    prerequisites.compile_or_validate_app(
        True,
        check_if_schema_up_to_date=True,
        prerender_routes=False,
    )
    _write_env_json()
    from reflex_django.frontend_stability import apply_frontend_stability_after_compile

    apply_frontend_stability_after_compile()


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
    roots: list[Path] = []

    try:
        from django.conf import settings

        base = getattr(settings, "BASE_DIR", None)
        if base:
            roots.append(Path(str(base)).resolve())
    except Exception:  # noqa: BLE001
        pass

    cwd = Path.cwd().resolve()
    if cwd not in roots:
        roots.append(cwd)

    return roots


def _recompile_in_subprocess(port: int) -> None:
    """Recompile the SPA in a fresh interpreter so edited modules are reloaded.

    Recompiling in-process would re-use the already-imported (stale) Reflex
    page/state modules, so the regenerated ``.web`` would not reflect the
    edit. Spawning ``python -m reflex_django._frontend_runner --compile-only``
    gives us a clean import every time; Vite (still running in this process)
    then hot-reloads from the freshly written ``.web`` output.
    """
    cmd = [
        sys.executable,
        "-m",
        "reflex_django._frontend_runner",
        "--frontend-port",
        str(port),
        "--compile-only",
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(
            "reflex-django: recompile failed; keeping the previous `.web` "
            "bundle. Fix the error above and save again.",
            file=sys.stderr,
        )
    else:
        print("reflex-django: recompiled `.web` — Vite hot-reloading frontend.")


def _start_watch_thread(port: int) -> threading.Thread | None:
    """Start a daemon thread that recompiles ``.web`` on Reflex source changes.

    Returns the thread (already started) or ``None`` if ``watchfiles`` is not
    installed, in which case the caller proceeds without a recompile loop.
    """
    try:
        from watchfiles import PythonFilter, watch
    except Exception:  # noqa: BLE001
        print(
            "reflex-django: `watchfiles` is not installed — frontend "
            "hot-reload-on-edit is disabled. Install `uvicorn[standard]` (or "
            "`watchfiles`) to recompile the SPA automatically on save.",
            file=sys.stderr,
        )
        return None

    watch_paths = [str(p) for p in _resolve_watch_paths()]

    def _loop() -> None:
        try:
            for changes in watch(
                *watch_paths,
                watch_filter=PythonFilter(),
                debounce=800,
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

    if args.compile_only:
        # Re-raise SystemExit so a non-zero exit propagates to the watch loop.
        _compile_app_for_frontend()
        return 0

    _compile_once_safe()

    if args.watch:
        _start_watch_thread(args.frontend_port)

    try:
        return _run_vite(args.frontend_port)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
