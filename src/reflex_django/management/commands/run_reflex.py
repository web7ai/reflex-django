"""Run the unified Reflex + Django dev server via ``manage.py``.

In :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER` (the default),
the default Vite-HMR dev loop delegates to ``reflex run`` with the backend
patched to serve :func:`reflex_django.asgi_entry.application`. Custom
orchestration remains for ``--from-build``, ``--single-port`` dev, and
``--env prod``.

In legacy routing modes (``reflex_led`` / ``django_led``), the command
delegates to Reflex's own CLI unchanged.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError


_DEFAULT_FRONTEND_PORT = 3000
_DEFAULT_BACKEND_PORT = 8000


class Command(BaseCommand):
    """Start Reflex and Django in one process (single-port architecture)."""

    help = "Run the Reflex app with the Django ASGI backend in a single process."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--env",
            choices=["dev", "prod"],
            default=None,
            help="Reflex environment (dev or prod).",
        )
        parser.add_argument(
            "--frontend-port",
            dest="frontend_port",
            default=None,
            help="Frontend port (Reflex/Vite dev server).",
        )
        parser.add_argument(
            "--backend-port",
            dest="backend_port",
            default=None,
            help="Backend port (ASGI server).",
        )
        parser.add_argument(
            "--backend-host",
            dest="backend_host",
            default=None,
            help="Backend bind host.",
        )
        parser.add_argument(
            "--loglevel",
            choices=["debug", "info", "warning", "error", "critical"],
            default=None,
            help="Log level for the ASGI server.",
        )
        parser.add_argument(
            "--frontend-only",
            action="store_true",
            help="Run only the Reflex frontend (Vite dev server).",
        )
        parser.add_argument(
            "--backend-only",
            action="store_true",
            help="Run only the ASGI backend (Django + Reflex). No Vite, no HMR.",
        )
        parser.add_argument(
            "--no-reload",
            action="store_true",
            dest="no_reload",
            help="Disable ASGI server auto-reload on file changes.",
        )
        parser.add_argument(
            "--from-build",
            "--serve-build",
            action="store_true",
            dest="from_build",
            help=(
                "Skip Vite entirely. Re-export the SPA bundle (frontend-only, "
                "no zip, staged into STATIC_ROOT/_reflex) before starting the "
                "ASGI server, then serve it from disk. Re-run the command to "
                "rebuild after Reflex page changes. Opt in here, or set "
                "REFLEX_DJANGO_SERVE_FROM_BUILD = True; otherwise the default "
                "is the Vite-HMR dev loop."
            ),
        )
        parser.add_argument(
            "--with-vite",
            "--no-from-build",
            action="store_true",
            dest="with_vite",
            help=(
                "Spawn Vite for hot-module reload (the default dev loop). "
                "Useful to force the Vite loop when "
                "REFLEX_DJANGO_SERVE_FROM_BUILD = True is set in settings."
            ),
        )
        parser.add_argument(
            "--skip-rebuild",
            action="store_true",
            dest="skip_rebuild",
            help=(
                "When --from-build is active, do NOT re-export before serving "
                "(use the existing bundle on disk). Useful for fast restarts "
                "after only Python changes."
            ),
        )
        parser.add_argument(
            "reflex_args",
            nargs="*",
            help="Additional arguments forwarded to ``reflex run`` (prefix with --).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from reflex_django.integration import (
            install_reflex_django_integration,
            refresh_get_config_bindings,
        )
        from reflex_django.routing import UrlRoutingMode, resolve_url_routing

        install_reflex_django_integration()
        refresh_get_config_bindings()

        mode = resolve_url_routing()
        if mode == UrlRoutingMode.DJANGO_OUTER:
            self._run_django_outer(options)
            return
        self._invoke_reflex_run(options)

    # ------------------------------------------------------------------
    # Django-outer single-port mode
    # ------------------------------------------------------------------

    def _run_django_outer(self, options: dict[str, Any]) -> None:
        """Spawn Vite + uvicorn/granian wired around the Django-outer ASGI app."""
        env_name = options.get("env") or "dev"
        is_prod = env_name == "prod"

        backend_port = int(
            options.get("backend_port")
            or os.environ.get("REFLEX_DJANGO_BACKEND_PORT")
            or _DEFAULT_BACKEND_PORT
        )
        backend_host = (
            options.get("backend_host")
            or os.environ.get("REFLEX_DJANGO_BACKEND_HOST")
            or "0.0.0.0"
        )
        frontend_port = int(
            options.get("frontend_port")
            or os.environ.get("REFLEX_DJANGO_FRONTEND_PORT")
            or _DEFAULT_FRONTEND_PORT
        )
        loglevel = options.get("loglevel") or "info"
        frontend_only = bool(options.get("frontend_only"))
        backend_only = bool(options.get("backend_only"))
        skip_rebuild = bool(options.get("skip_rebuild"))

        # Resolve from-build mode. Precedence, highest first:
        #   1. ``--env prod``                       → True  (always export and serve from disk)
        #   2. ``--env dev`` (explicit)             → False (compile-only loop; browse ``:8000``)
        #   3. ``--with-vite`` / ``--no-from-build``→ False (explicit two-port Vite opt-in)
        #   4. ``--from-build``                     → True  (explicit serve-from-disk export)
        #   5. ``REFLEX_DJANGO_SERVE_FROM_BUILD``   → from settings/env (default False)
        with_vite = bool(options.get("with_vite"))
        explicit_from_build = bool(options.get("from_build"))
        is_env_dev = options.get("env") == "dev"
        is_single_port_dev = is_env_dev and not with_vite
        if is_prod:
            from_build = True
        elif is_env_dev:
            from_build = False
        elif with_vite and not explicit_from_build:
            from_build = False
        elif explicit_from_build:
            from_build = True
        else:
            from_build = self._setting_serve_from_build()

        os.environ.setdefault("REFLEX_DJANGO_FRONTEND_PORT", str(frontend_port))
        os.environ.setdefault("REFLEX_DJANGO_BACKEND_PORT", str(backend_port))

        # ``run_reflex`` owns SPA builds itself (Vite for HMR, or the explicit
        # ``_auto_export_for_build_mode`` for --env prod/--from-build), so turn
        # off the ASGI startup auto-export hook that exists for raw
        # ``uvicorn ...:application`` deploys. Otherwise the in-process ASGI
        # boot could trigger a second, redundant export — or build a bundle in
        # the Vite-HMR loop where one isn't needed. ``setdefault`` lets an
        # operator who explicitly set the env keep their choice.
        os.environ.setdefault("REFLEX_DJANGO_AUTO_EXPORT_ON_START", "0")

        # ``--env prod`` and ``--from-build`` both serve the SPA from disk and
        # must not try to reach Vite. We treat them uniformly here: no Vite
        # spawn, no dev proxy, and a pre-flight SPA check. ``--env prod``
        # additionally flips DEBUG off so the default settings stop honoring
        # development conveniences.
        serve_from_disk = is_prod or from_build or is_single_port_dev
        if serve_from_disk:
            os.environ["REFLEX_DJANGO_DEV_PROXY"] = "0"
            os.environ["REFLEX_DJANGO_SEPARATE_DEV_PORTS"] = "0"
        if is_single_port_dev:
            os.environ["REFLEX_DJANGO_COMPILE_DEV"] = "1"
        if is_prod:
            os.environ.setdefault("REFLEX_DJANGO_DEBUG", "0")

        # Print an up-front banner BEFORE the (potentially slow) auto-export
        # kicks in so the user sees what mode they are in. Plain
        # ``manage.py run_reflex`` (no flags) lands in the Vite-HMR branch by
        # default; ``--from-build`` opts into the serve-from-disk loop.
        if is_single_port_dev and not backend_only:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    "reflex-django: single-port compile dev (--env dev) - "
                    f"compiles to `.web/` on each save and serves from Django "
                    f"on port {backend_port}.\n"
                    "    No ``react-router build`` per edit. Run "
                    "`export_reflex --frontend-only --no-zip --env dev` once "
                    "if no bundle exists yet. Pass `--with-vite` for live "
                    f"Vite HMR on :{frontend_port} instead."
                )
            )
        elif from_build and not is_prod:
            mode_label = (
                "--from-build (explicit)"
                if explicit_from_build
                else "from-build (REFLEX_DJANGO_SERVE_FROM_BUILD)"
            )
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"reflex-django: {mode_label} — Django will auto-export the "
                    "SPA and serve the compiled bundle from disk. No Vite, no HMR.\n"
                    "    Omit --from-build for the default Vite-HMR dev loop, or "
                    "--skip-rebuild to reuse the existing bundle on disk."
                )
            )
        elif not is_prod and not backend_only:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    "reflex-django: Vite-HMR dev loop (default) — editing a "
                    "Reflex page recompiles the SPA and Vite hot-reloads the "
                    "frontend; backend/state edits restart uvicorn automatically.\n"
                    "    Pass --from-build to serve a compiled bundle from disk "
                    "instead (no Node, no HMR)."
                )
            )

        if from_build and not skip_rebuild and not is_single_port_dev:
            # Rebuild the SPA before serving so the user sees the latest
            # Reflex page tree on every ``manage.py run_reflex``.
            self._auto_export_for_build_mode(env=env_name)
        if is_single_port_dev and not skip_rebuild and not backend_only:
            self._compile_dev_once()
        if serve_from_disk:
            self._warn_if_spa_missing()

        if frontend_only and from_build:
            # ``--from-build --frontend-only`` reduces to "just rebuild
            # the bundle and exit" — useful in CI/pre-deploy steps.
            self.stdout.write(
                self.style.SUCCESS(
                    "reflex-django: --from-build --frontend-only finished. "
                    "Bundle is staged; start the ASGI server when ready."
                )
            )
            return

        if not serve_from_disk and not frontend_only and not is_single_port_dev:
            os.environ["REFLEX_DJANGO_SEPARATE_DEV_PORTS"] = "1"
            os.environ["REFLEX_DJANGO_DEV_PROXY"] = "0"
            from reflex_django.auto_mount import refresh_reflex_mount_catchall

            refresh_reflex_mount_catchall()
            self._invoke_reflex_run(options)
            return

        if frontend_only:
            self._spawn_vite_blocking(
                frontend_port, watch=not options.get("no_reload")
            )
            return

        # ``--env dev`` compiles to ``.web/`` only (no ``react-router build``).
        vite_active = not serve_from_disk and not backend_only and not is_single_port_dev
        watch_frontend = vite_active and not options.get("no_reload")

        vite_proc: subprocess.Popen[bytes] | None = None
        if vite_active:
            os.environ["REFLEX_DJANGO_SEPARATE_DEV_PORTS"] = "1"
            os.environ["REFLEX_DJANGO_DEV_PROXY"] = "0"
            # Mirror native ``reflex run``: compile once in the parent, then boot
            # Vite and the ASGI backend concurrently (do not block the backend on
            # Vite becoming HTTP-ready).
            self._compile_dev_app_once()
            self._ensure_frontend_port_free(frontend_port)
            self._print_dev_port_banner(
                frontend_port=frontend_port,
                backend_port=backend_port,
            )
            vite_proc = self._spawn_vite_background(
                frontend_port,
                watch=watch_frontend,
                skip_compile=True,
            )
            self._start_vite_ready_notifier(frontend_port, vite_proc=vite_proc)
        elif is_single_port_dev and not backend_only:
            self.stdout.write(
                self.style.SUCCESS(
                    f"reflex-django: compile dev — serving SPA from disk on "
                    f"port {backend_port} (recompile-only, no JS build per save)."
                )
            )
            if not options.get("no_reload") and not is_prod:
                from reflex_django import _frontend_runner as frontend_runner

                frontend_runner.start_compile_dev_watch()
        elif is_prod:
            self.stdout.write(
                self.style.SUCCESS(
                    f"reflex-django: production mode — serving compiled SPA "
                    f"from disk (no Vite). ASGI server on port {backend_port}."
                )
            )
        elif from_build:
            self.stdout.write(
                self.style.SUCCESS(
                    f"reflex-django: serving SPA from disk "
                    f"(no Vite). ASGI server on port {backend_port}.\n"
                    "    Re-run `python manage.py run_reflex` to rebuild after "
                    "any Reflex page change. Python/Django edits auto-reload."
                )
            )

        # Catch-all was built during Django startup (before CLI env above).
        # Rebuild it so prod/single-port/from-build own ``/`` on the backend port.
        from reflex_django.auto_mount import refresh_reflex_mount_catchall

        refresh_reflex_mount_catchall()

        reload_enabled = not options.get("no_reload") and not is_prod
        # In from-build dev mode we MUST own the reload loop ourselves. If we
        # delegated to uvicorn's ``--reload``, the child would re-import
        # :mod:`reflex_django.asgi_entry` on every file change, which re-runs
        # the reflex-django bootstrap inside a process that already has the
        # SPA cached on disk. That often appears "stuck" (the bootstrap can
        # deadlock on duplicate Reflex compiler patches) and — crucially —
        # never re-exports the SPA, so the user sees the old bundle even
        # after the reload succeeds. Running uvicorn as a subprocess with a
        # parent-side :mod:`watchfiles` loop gives us a clean process restart
        # AND a guaranteed re-export on every change.
        use_parent_watch = (
            from_build
            and reload_enabled
            and not backend_only
            and not is_single_port_dev
        )
        # With Vite active, uvicorn in-process ``--reload`` is much faster than
        # spawning a fresh subprocess.  Frontend and backend watchers are split
        # via ``reload_excludes`` / the frontend-runner filter so they no longer
        # race on the same save.
        backend_reload = reload_enabled and not use_parent_watch

        # Compile-dev uses a subprocess without uvicorn reload — the recompile
        # watch thread handles ``views.py`` edits, and in-process ``reload=True``
        # hangs on Windows before the server binds.
        backend_proc: subprocess.Popen[bytes] | None = None
        try:
            if use_parent_watch:
                self._run_with_watch_reload(
                    host=backend_host,
                    port=backend_port,
                    loglevel=loglevel,
                    skip_rebuild=skip_rebuild,
                    env=env_name,
                )
            elif is_single_port_dev and not backend_only:
                backend_proc = self._spawn_uvicorn_dev_subprocess(
                    host=backend_host,
                    port=backend_port,
                    loglevel=loglevel,
                    reload=False,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"reflex-django: open http://127.0.0.1:{backend_port}/ "
                        "(Ctrl+C to stop)."
                    )
                )
                self.stdout.flush()
                try:
                    backend_proc.wait()
                except KeyboardInterrupt:
                    pass
            elif vite_active and vite_proc is not None:
                # In-process ``uvicorn.run(..., reload=True)`` while a Vite child
                # process is running can hang on Windows before binding :8000.
                # Spawn uvicorn separately (native Reflex runs frontend+backend
                # concurrently) and supervise both from the parent.
                backend_proc = self._spawn_uvicorn_dev_subprocess(
                    host=backend_host,
                    port=backend_port,
                    loglevel=loglevel,
                    reload=backend_reload,
                )
                self._supervise_vite_dev_procs(
                    vite_proc=vite_proc,
                    backend_proc=backend_proc,
                )
            else:
                self._run_asgi_server(
                    host=backend_host,
                    port=backend_port,
                    loglevel=loglevel,
                    reload=backend_reload,
                    reload_backend_only=vite_active,
                )
        finally:
            self._stop_uvicorn_subprocess(backend_proc)
            for proc, label in (
                (vite_proc, "Vite"),
            ):
                if proc is not None and proc.poll() is None:
                    self.stdout.write(
                        self.style.NOTICE(f"reflex-django: stopping {label}.")
                    )
                    try:
                        if sys.platform == "win32":
                            proc.terminate()
                        else:
                            proc.send_signal(signal.SIGINT)
                        proc.wait(timeout=5)
                    except Exception:  # noqa: BLE001
                        proc.kill()

    def _setting_serve_from_build(self) -> bool:
        """Return whether ``settings.REFLEX_DJANGO_SERVE_FROM_BUILD`` is on.

        Honours the env var ``REFLEX_DJANGO_SERVE_FROM_BUILD`` as well so
        operators can toggle the behaviour without editing ``settings.py``.

        The library default is ``False`` (the Vite-HMR dev loop is the
        canonical dev story); if the setting is missing entirely we still
        return ``False`` so a fresh project that hasn't added the key yet
        gets the Vite default. Pass ``--from-build`` (or set the key/env to a
        truthy value) to opt into the serve-from-disk build loop.
        """
        env = os.environ.get("REFLEX_DJANGO_SERVE_FROM_BUILD")
        if env is not None:
            return str(env).strip().lower() not in {"0", "false", "no"}
        try:
            from django.conf import settings

            return bool(getattr(settings, "REFLEX_DJANGO_SERVE_FROM_BUILD", False))
        except Exception:  # noqa: BLE001
            return False

    def _auto_export_for_build_mode(self, env: str = "prod") -> None:
        """Run the export command in-process before serving the SPA.

        Equivalent to running:

        .. code-block:: bash

            python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root

        but stays inside the current Python process so the Reflex/Django
        integration patches are reused — no second interpreter bootstrap.

        Failures are not fatal: if the export crashes we fall back to whatever
        is already on disk (``ReflexMountView`` returns 404 with a helpful
        message if nothing is there). This means an HMR-less dev loop is
        still recoverable when one component breaks the build — re-run with
        ``--from-build --skip-rebuild`` to use the previous good bundle.
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError

        try:
            from django.conf import settings
            has_static_root = bool(getattr(settings, "STATIC_ROOT", None))
        except Exception:
            has_static_root = False

        # Dev/from-build serves from ``.web/`` only; prod may stage into STATIC_ROOT.
        stage_to_static = env != "dev" and has_static_root
        if env == "dev":
            stage_desc = "built to .web (not staged to STATIC_ROOT)"
        elif stage_to_static:
            stage_desc = "staged into STATIC_ROOT/_reflex"
        else:
            stage_desc = "unstaged"
        self.stdout.write(
            self.style.NOTICE(
                f"reflex-django: auto-exporting Reflex SPA "
                f"(frontend-only, no-zip, {stage_desc}, env={env})..."
            )
        )
        start = time.monotonic()
        try:
            call_command(
                "export_reflex",
                frontend_only=True,
                no_zip=True,
                stage_to_static_root=stage_to_static,
                env=env,
            )
        except CommandError as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"reflex-django: auto-export failed: {exc}\n"
                    "    Falling back to the existing bundle on disk (if any). "
                    "Re-run with --skip-rebuild to suppress this attempt."
                )
            )
            return
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(
                self.style.ERROR(
                    f"reflex-django: auto-export crashed: {exc!r}\n"
                    "    Falling back to the existing bundle on disk (if any)."
                )
            )
            return
        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: auto-export finished in {elapsed:.1f}s."
            )
        )

    def _spa_index_missing(self) -> bool:
        """Return True when no compiled SPA ``index.html`` is on disk.

        Uses the same discovery paths as
        :class:`reflex_django.views.mount.ReflexMountView` so the pre-flight
        check matches what the runtime view will actually find. Errors are
        treated as "missing" so we err on the side of (re)building.
        """
        try:
            from reflex_django.views.mount import _resolve_spa_index
        except Exception:  # noqa: BLE001
            return True
        try:
            return _resolve_spa_index() is None
        except Exception:  # noqa: BLE001
            return True

    def _warn_if_spa_missing(self) -> None:
        """Print a clear warning when ``--env prod`` cannot find a compiled SPA.

        :class:`reflex_django.views.mount.ReflexMountView` discovers the
        compiled bundle at a handful of well-known paths (``STATIC_ROOT/_reflex``,
        ``STATIC_ROOT/_static``, ``BASE_DIR/.web/_static`` …). When the user
        runs ``manage.py run_reflex --env prod`` before running
        ``reflex export --frontend-only``/``collectstatic``, the catch-all
        view returns 404 with a hint, but the first signal the user usually
        sees is a confusing ``ConnectError`` from the (now disabled) dev
        proxy. We pre-check the disk and emit a single, clear warning instead.
        """
        try:
            from reflex_django.views.mount import _resolve_spa_index
        except Exception:  # noqa: BLE001
            return
        index = _resolve_spa_index()
        if index is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"reflex-django: found compiled SPA at {index}"
                )
            )
            return
        self.stdout.write(
            self.style.WARNING(
                "reflex-django: WARNING — no compiled SPA was found in any of the "
                "expected locations (STATIC_ROOT/_reflex, STATIC_ROOT/_static, "
                "STATIC_ROOT/reflex, STATIC_ROOT, .web/build/client, "
                ".web/_static, .web/build).\n"
                "The catch-all view will return 404 for `/`. To build the SPA:\n"
                "    python manage.py export_reflex --frontend-only --no-zip --stage-to-static-root\n"
                "    python manage.py collectstatic --noinput\n"
                "Or run without `--env prod` for dev mode (Vite-proxied)."
            )
        )

    def _compile_dev_app_once(self) -> None:
        """Compile the SPA once before spawning Vite + uvicorn (native Reflex flow)."""
        from reflex_django._frontend_runner import _compile_app_for_frontend

        self.stdout.write(
            self.style.NOTICE("reflex-django: compiling Reflex app...")
        )
        start = time.monotonic()
        try:
            _compile_app_for_frontend()
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"reflex-django: frontend compile failed: {exc!r}"
            ) from exc
        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: compile finished in {elapsed:.1f}s — starting "
                "frontend and backend together."
            )
        )
        self.stdout.flush()

    def _compile_dev_once(self) -> None:
        """Compile the Reflex app to ``.web/`` (no ``react-router build``)."""
        from reflex_django import _frontend_runner as frontend_runner

        self.stdout.write(
            self.style.NOTICE(
                "reflex-django: compiling Reflex app to `.web/` (env=dev)..."
            )
        )
        start = time.monotonic()
        try:
            frontend_runner._compile_app_for_frontend()
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CommandError(
                f"reflex-django: frontend compile failed: {exc!r}"
            ) from exc
        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: compile finished in {elapsed:.1f}s."
            )
        )
        self.stdout.flush()

    def _compile_dev_disk_bundle_once(self) -> None:
        """Backward-compatible alias for :meth:`_compile_dev_once`."""
        self._compile_dev_once()

    def _print_dev_port_banner(
        self,
        *,
        frontend_port: int,
        backend_port: int,
    ) -> None:
        """Print target URLs before services finish booting."""
        self.stdout.write(
            self.style.NOTICE(
                "reflex-django: two-port dev (native Reflex layout).\n"
                f"    Open the app: http://localhost:{frontend_port}/\n"
                f"    Backend: http://localhost:{backend_port}/ "
                f"(admin, API, /_event — browser connects here directly)."
            )
        )

    def _start_vite_ready_notifier(
        self,
        frontend_port: int,
        *,
        vite_proc: subprocess.Popen[bytes],
    ) -> None:
        """Notify when Vite is HTTP-ready without blocking backend startup."""

        def _notify() -> None:
            try:
                self._wait_for_vite_ready(frontend_port, vite_proc=vite_proc)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"reflex-django: Vite ready at "
                        f"http://localhost:{frontend_port}/"
                    )
                )
            except CommandError as exc:
                self.stdout.write(self.style.ERROR(str(exc)))

        thread = threading.Thread(
            target=_notify,
            name="reflex-django-vite-ready",
            daemon=True,
        )
        thread.start()

    def _ensure_frontend_port_free(self, frontend_port: int) -> None:
        """Fail fast when another process already owns the Vite port."""
        import socket

        host = os.environ.get("REFLEX_DJANGO_FRONTEND_HOST", "127.0.0.1")
        try:
            with socket.create_connection((host, frontend_port), timeout=0.5):
                occupied = True
        except OSError:
            occupied = False
        if occupied:
            raise CommandError(
                f"reflex-django: port {frontend_port} is already in use. "
                "Stop the other dev server (an old Vite or `run_reflex` "
                "instance) and re-run `python manage.py run_reflex`."
            )

    @staticmethod
    def _vite_http_ready(target: str) -> bool:
        """Return True when *target* serves a Vite/React SPA root document."""
        from reflex_django.asgi_entry import _vite_target_reachable

        if not _vite_target_reachable(target):
            return False
        try:
            import httpx

            response = httpx.get(f"{target.rstrip('/')}/", timeout=2.0)
        except Exception:  # noqa: BLE001
            return False
        if response.status_code != 200:
            return False
        body = response.text.lower()
        return any(
            marker in body
            for marker in ("react-router", "@vite", "modulepreload", "vite/client")
        )

    def _wait_for_vite_ready(
        self,
        frontend_port: int,
        *,
        vite_proc: subprocess.Popen[bytes],
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> None:
        """Block until Vite serves the SPA on the expected port."""
        host = os.environ.get("REFLEX_DJANGO_FRONTEND_HOST", "127.0.0.1")
        target = f"http://{host}:{frontend_port}"
        deadline = time.monotonic() + timeout
        announced = False

        while time.monotonic() < deadline:
            if vite_proc.poll() is not None:
                raise CommandError(
                    f"reflex-django: Vite subprocess exited before becoming "
                    f"ready on port {frontend_port}. Check the Vite logs above."
                )
            if self._vite_http_ready(target):
                return
            if not announced:
                self.stdout.write(
                    self.style.NOTICE(
                        f"reflex-django: waiting for Vite on port {frontend_port}..."
                    )
                )
                announced = True
            time.sleep(poll_interval)

        raise CommandError(
            f"reflex-django: timed out after {timeout:.0f}s waiting for Vite "
            f"on port {frontend_port}. Ensure Node/Bun is installed, port "
            f"{frontend_port} is free, and no stale Vite process is running, "
            "then re-run `python manage.py run_reflex`."
        )

    def _spawn_vite_background(
        self,
        frontend_port: int,
        *,
        watch: bool = True,
        skip_compile: bool = False,
    ) -> subprocess.Popen[bytes]:
        """Spawn Vite behind the proxy via the reflex-django bootstrap runner.

        We spawn :mod:`reflex_django._frontend_runner` instead of ``reflex``
        directly so the subprocess loads the reflex-django integration first
        (otherwise Reflex CLI fails with ``rxconfig.py not found`` because the
        :func:`~reflex_django.cli_layout.ensure_reflex_cli_layout` import patch
        is not in place).

        When ``watch`` is True (the default) the runner also watches the
        Reflex source tree and recompiles ``.web`` on change so Vite hot
        reloads the frontend without restarting the backend. Pass
        ``watch=False`` (``run_reflex --no-reload``) for a one-shot compile +
        Vite with no recompile loop.
        """
        cmd = [
            sys.executable,
            "-m",
            "reflex_django._frontend_runner",
            "--frontend-port",
            str(frontend_port),
        ]
        if not watch:
            cmd.append("--no-watch")
        if skip_compile:
            cmd.append("--skip-compile")
        env = {
            **os.environ,
            "REFLEX_DJANGO_URL_ROUTING": "django_outer",
            "REFLEX_DJANGO_FRONTEND_PORT": str(frontend_port),
        }
        return subprocess.Popen(cmd, env=env)

    def _spawn_vite_blocking(
        self,
        frontend_port: int,
        *,
        watch: bool = True,
    ) -> None:
        """Run Vite in the foreground (``--frontend-only`` from the user)."""
        cmd = [
            sys.executable,
            "-m",
            "reflex_django._frontend_runner",
            "--frontend-port",
            str(frontend_port),
        ]
        if not watch:
            cmd.append("--no-watch")
        subprocess.run(cmd, check=False)

    def _run_asgi_server(
        self,
        *,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
        reload_backend_only: bool = False,
    ) -> None:
        """Boot the ASGI server with :func:`reflex_django.asgi_entry.application`."""
        target = "reflex_django.asgi_entry:application"

        for runner in (self._run_uvicorn, self._run_granian, self._run_hypercorn):
            try:
                runner(
                    target=target,
                    host=host,
                    port=port,
                    loglevel=loglevel,
                    reload=reload,
                    reload_backend_only=reload_backend_only,
                )
                return
            except _ServerNotAvailable:
                continue

        raise CommandError(
            "reflex-django requires one of `uvicorn`, `granian`, or `hypercorn` to "
            "serve the ASGI app. Install with `pip install uvicorn[standard]` and "
            "re-run `python manage.py run_reflex`."
        )

    # ------------------------------------------------------------------
    # Parent-side watch loop (from-build dev)
    # ------------------------------------------------------------------

    def _run_with_watch_reload(
        self,
        *,
        host: str,
        port: int,
        loglevel: str,
        skip_rebuild: bool,
        env: str = "dev",
    ) -> None:
        """Run uvicorn as a subprocess and re-export + restart on file changes.

        Why this exists instead of uvicorn's built-in ``--reload``:

        * Uvicorn's reloader re-imports the ASGI app inside a child interpreter
          on every change. For reflex-django this re-runs
          :func:`~reflex_django.integration.install_reflex_django_integration`,
          which monkey-patches Reflex's compiler/config modules. The second
          application of those patches can race or deadlock, manifesting as a
          "WatchFiles detected changes ... Reloading" line that never returns.
        * Uvicorn's reloader has no hook for "rebuild the SPA before the next
          child boots", so even when it succeeds the user sees the *old*
          compiled bundle until they kill and re-run the command.

        Owning the reload loop in the parent fixes both: each restart is a
        brand-new uvicorn subprocess (no module-state leakage) and we re-run
        :meth:`_auto_export_for_build_mode` between cycles so the served SPA
        always reflects the latest source.
        """
        try:
            from watchfiles import PythonFilter, watch
        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "reflex-django: `watchfiles` is not installed — falling back "
                    "to uvicorn's in-process reloader. Install `uvicorn[standard]` "
                    "for the from-build watch+rebuild loop."
                )
            )
            self._run_asgi_server(
                host=host, port=port, loglevel=loglevel, reload=True
            )
            return

        watch_root = self._resolve_watch_root()
        watch_filter = self._build_watch_filter(PythonFilter)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"reflex-django: from-build watch loop — Django watches "
                f"{watch_root} for .py changes; every change triggers an "
                "auto-export + clean uvicorn restart."
            )
        )

        proc = self._spawn_uvicorn_subprocess(
            host=host, port=port, loglevel=loglevel
        )
        try:
            from reflex_django.dev_watch import WATCH_DEBOUNCE_MS

            for changes in watch(
                str(watch_root),
                watch_filter=watch_filter,
                debounce=WATCH_DEBOUNCE_MS,
                step=50,
                yield_on_timeout=False,
                raise_interrupt=False,
            ):
                if not changes:
                    continue
                changed_paths = sorted({path for _kind, path in changes})
                preview = ", ".join(self._shorten(p, watch_root) for p in changed_paths[:3])
                if len(changed_paths) > 3:
                    preview += f" (+{len(changed_paths) - 3} more)"
                self.stdout.write(
                    self.style.NOTICE(
                        f"reflex-django: detected change in {preview} — "
                        "stopping uvicorn, re-exporting SPA, restarting."
                    )
                )

                self._stop_uvicorn_subprocess(proc)
                if not skip_rebuild:
                    self._auto_export_for_build_mode(env=env)
                proc = self._spawn_uvicorn_subprocess(
                    host=host, port=port, loglevel=loglevel
                )
        except KeyboardInterrupt:
            pass
        finally:
            self._stop_uvicorn_subprocess(proc)

    def _resolve_watch_root(self) -> Path:
        """Return the directory we should watch for source changes.

        Prefers ``settings.BASE_DIR`` (the user's Django project root). Falls
        back to the current working directory when that setting is missing
        or unreadable.
        """
        try:
            from django.conf import settings

            base = getattr(settings, "BASE_DIR", None)
            if base:
                return Path(str(base)).resolve()
        except Exception:  # noqa: BLE001
            pass
        return Path.cwd().resolve()

    def _build_watch_filter(self, python_filter_cls: type):
        """Return a watchfiles filter that ignores reflex-django build artefacts.

        We subclass :class:`watchfiles.PythonFilter` so we still get the
        sensible default of "Python files only, ignoring ``.git``, virtual
        envs, ``__pycache__`` and friends", then add our own excludes for
        directories the auto-export itself writes to (otherwise the export
        would trigger another reload mid-build, looping forever).
        """
        try:
            from django.conf import settings
        except Exception:  # noqa: BLE001
            settings = None  # type: ignore[assignment]

        extra_excludes: list[str] = [
            os.sep + ".web" + os.sep,
            os.sep + "node_modules" + os.sep,
            os.sep + "staticfiles" + os.sep,
            os.sep + "static_collected" + os.sep,
            os.sep + ".reflex" + os.sep,
            os.sep + "dist" + os.sep,
            os.sep + "build" + os.sep,
        ]
        if settings is not None:
            static_root = getattr(settings, "STATIC_ROOT", None)
            if static_root:
                extra_excludes.append(
                    os.path.normpath(str(static_root)) + os.sep
                )

        class _ReflexDjangoFilter(python_filter_cls):  # type: ignore[misc, valid-type]
            def __call__(self, change, path: str) -> bool:  # noqa: D401, ANN001
                norm = os.path.normpath(path)
                for needle in extra_excludes:
                    if needle in norm:
                        return False
                return super().__call__(change, path)

        return _ReflexDjangoFilter()

    @staticmethod
    def _shorten(path: str, root: Path) -> str:
        """Return ``path`` relative to ``root`` for readable log lines."""
        try:
            return str(Path(path).relative_to(root))
        except ValueError:
            return path

    def _supervise_vite_dev_procs(
        self,
        *,
        vite_proc: subprocess.Popen[bytes],
        backend_proc: subprocess.Popen[bytes],
    ) -> None:
        """Keep Vite + uvicorn subprocesses alive until interrupt or child exit."""
        try:
            while True:
                vite_code = vite_proc.poll()
                if vite_code is not None:
                    raise CommandError(
                        f"reflex-django: Vite subprocess exited unexpectedly "
                        f"(code {vite_code}). Check the Vite logs above."
                    )
                backend_code = backend_proc.poll()
                if backend_code is not None:
                    raise CommandError(
                        f"reflex-django: uvicorn subprocess exited unexpectedly "
                        f"(code {backend_code}). Check the backend logs above."
                    )
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    def _spawn_uvicorn_dev_subprocess(
        self,
        *,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
    ) -> subprocess.Popen[bytes]:
        """Spawn uvicorn for two-port dev while Vite runs in a sibling process."""
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "reflex_django.asgi_entry:application",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            loglevel,
            "--ws",
            "auto",
        ]
        if reload:
            from reflex_django.dev_watch import BACKEND_RELOAD_DELAY_S

            cmd.append("--reload")
            cmd.extend(["--reload-dir", str(self._resolve_watch_root())])
            cmd.extend(["--reload-delay", str(BACKEND_RELOAD_DELAY_S)])
            # Uvicorn's CLI expands ``**`` globs on Windows into stray positional
            # args, so backend-only excludes are applied via in-process reload in
            # non-Vite modes; here we rely on ``--reload-dir`` + frontend watch
            # filtering to avoid double work on ``views.py`` edits.
            if sys.platform != "win32":
                from reflex_django.dev_watch import backend_reload_excludes

                for pattern in backend_reload_excludes():
                    cmd.extend(["--reload-exclude", pattern])

        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: starting uvicorn subprocess at "
                f"http://{host}:{port}/"
            )
        )
        self.stdout.flush()
        env = {
            **os.environ,
            "REFLEX_DJANGO_AUTO_EXPORT_ON_START": os.environ.get(
                "REFLEX_DJANGO_AUTO_EXPORT_ON_START", "0"
            ),
        }
        return subprocess.Popen(cmd, env=env)

    def _spawn_uvicorn_subprocess(
        self,
        *,
        host: str,
        port: int,
        loglevel: str,
    ) -> subprocess.Popen[bytes]:
        """Spawn uvicorn in a fresh interpreter so we control its lifecycle.

        Reload is intentionally OFF — the parent ``_run_with_watch_reload``
        loop is the only reload mechanism. This avoids the deadlock /
        stale-SPA problem documented above.
        """
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "reflex_django.asgi_entry:application",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            loglevel,
            "--ws",
            "auto",
        ]
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: starting uvicorn subprocess at "
                f"http://{host}:{port}/"
            )
        )
        env = {
            **os.environ,
            # Make sure the child also takes the from-build code path even
            # though it never actually hits ``_run_django_outer`` — this is
            # just defensive; the ASGI app does not branch on the setting.
            "REFLEX_DJANGO_SERVE_FROM_BUILD": os.environ.get(
                "REFLEX_DJANGO_SERVE_FROM_BUILD", "1"
            ),
            "REFLEX_DJANGO_DEV_PROXY": "0",
        }
        return subprocess.Popen(cmd, env=env)

    def _stop_uvicorn_subprocess(
        self, proc: subprocess.Popen[bytes] | None
    ) -> None:
        """Terminate the uvicorn subprocess quickly (dev reload loop)."""
        if proc is None or proc.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=2)
                return
            except subprocess.TimeoutExpired:
                pass
            proc.kill()
            with contextlib.suppress(Exception):
                proc.wait(timeout=2)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                proc.kill()

    def _run_uvicorn(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
        reload_backend_only: bool = False,
    ) -> None:
        try:
            import uvicorn  # type: ignore[import-not-found]
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {target} via uvicorn at "
                f"http://{host}:{port}/"
            )
        )
        run_kwargs: dict[str, Any] = {
            "host": host,
            "port": port,
            "log_level": loglevel,
            "reload": reload,
            "ws": "auto",
        }
        if reload:
            if reload_backend_only:
                from reflex_django.dev_watch import (
                    BACKEND_RELOAD_DELAY_S,
                    backend_reload_excludes,
                )

                run_kwargs["reload_dirs"] = [str(self._resolve_watch_root())]
                run_kwargs["reload_excludes"] = backend_reload_excludes()
                run_kwargs["reload_delay"] = BACKEND_RELOAD_DELAY_S
            else:
                run_kwargs["reload_excludes"] = [
                    "*/.web/*",
                    "*/node_modules/*",
                    "*/staticfiles/*",
                    "*/static_collected/*",
                ]
        uvicorn.run(target, **run_kwargs)

    def _run_granian(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
        reload_backend_only: bool = False,
    ) -> None:
        try:
            from granian.constants import Interfaces, Loops  # type: ignore[import-not-found]
            from granian.server import Granian  # type: ignore[import-not-found]
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {target} via granian at "
                f"http://{host}:{port}/"
            )
        )
        del loglevel, reload_backend_only  # granian uses its own log config
        Granian(
            target,
            address=host,
            port=port,
            interface=Interfaces.ASGI,
            loop=Loops.auto,
            reload=reload,
        ).serve()

    def _run_hypercorn(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
        reload_backend_only: bool = False,
    ) -> None:
        try:
            from hypercorn.asyncio import serve  # type: ignore[import-not-found]
            from hypercorn.config import Config  # type: ignore[import-not-found]
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        import asyncio
        import importlib

        cfg = Config()
        cfg.bind = [f"{host}:{port}"]
        cfg.loglevel = loglevel
        del reload_backend_only
        cfg.use_reloader = reload
        module_name, _, attr = target.partition(":")
        application = getattr(importlib.import_module(module_name), attr)
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {target} via hypercorn at "
                f"http://{host}:{port}/"
            )
        )
        asyncio.run(serve(application, cfg))

    # ------------------------------------------------------------------
    # Reflex CLI delegation
    # ------------------------------------------------------------------

    def _invoke_reflex_run(self, options: dict[str, Any]) -> None:
        """Defer to Reflex's ``run`` CLI (``reflex run``)."""
        try:
            from reflex.reflex import cli as reflex_cli
        except ImportError as exc:
            raise CommandError(
                "Reflex is not installed. Install reflex and reflex-django in this "
                "environment."
            ) from exc

        if reflex_cli.commands.get("run") is None:
            raise CommandError("Reflex CLI has no 'run' command.")

        if options.get("no_reload"):
            os.environ["REFLEX_DJANGO_BACKEND_RELOAD"] = "0"
        else:
            os.environ.pop("REFLEX_DJANGO_BACKEND_RELOAD", None)

        # Work around Reflex CLI raising "Cannot specify --frontend-port when not running frontend"
        # and "Cannot specify --backend-port when not running backend" due to default ports in config.
        try:
            import rxconfig
            if hasattr(rxconfig, "config") and rxconfig.config is not None:
                if options.get("frontend_only"):
                    rxconfig.config.backend_port = None
                elif options.get("backend_only"):
                    rxconfig.config.frontend_port = None
        except ImportError:
            pass

        import reflex_base.config as config_module
        from reflex_django.integration import _rebind_get_config_imports

        original_get_config = config_module.get_config

        def wrapped_get_config(reload: bool = False) -> Any:
            cfg = original_get_config(reload=reload)
            if options.get("frontend_only"):
                cfg.backend_port = None
            elif options.get("backend_only"):
                cfg.frontend_port = None
            return cfg

        config_module.get_config = wrapped_get_config
        _rebind_get_config_imports(wrapped_get_config)

        forward: list[str] = ["run"]
        if options.get("env"):
            forward.extend(["--env", options["env"]])
        if options.get("frontend_port"):
            forward.extend(["--frontend-port", str(options["frontend_port"])])
        if options.get("backend_port"):
            forward.extend(["--backend-port", str(options["backend_port"])])
        if options.get("backend_host"):
            forward.extend(["--backend-host", options["backend_host"]])
        if options.get("loglevel"):
            forward.extend(["--loglevel", options["loglevel"]])
        if options.get("frontend_only"):
            forward.append("--frontend-only")
        if options.get("backend_only"):
            forward.append("--backend-only")
        forward.extend(options.get("reflex_args") or [])

        old_argv = sys.argv
        try:
            sys.argv = ["reflex", *forward]
            reflex_cli.main(standalone_mode=True)
        finally:
            sys.argv = old_argv
            config_module.get_config = original_get_config
            _rebind_get_config_imports(original_get_config)


class _ServerNotAvailable(Exception):
    """Raised by a ``_run_*`` helper when its server package is not installed."""
