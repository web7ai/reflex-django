"""Run Reflex dev (frontend + Reflex backend) via ``manage.py``.

Runs ``reflex run`` with the native Reflex backend and Vite. Django admin/API
paths are served from the Reflex backend by default. Set ``RX_PROXY_SERVER``
only when Django runs on a separate HTTP server.
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from reflex_django.core.constants import (
    DEFAULT_BACKEND_PORT,
    DEFAULT_FRONTEND_PORT,
)
from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.dev.run_plan import RunPlan, build_run_plan

_DEFAULT_FRONTEND_PORT = DEFAULT_FRONTEND_PORT
_DEFAULT_BACKEND_PORT = DEFAULT_BACKEND_PORT


def _parse_asgi_target(target: str) -> tuple[str, str]:
    """Return ``(module, attr)`` from Django or ASGI-server path strings.

    Django ``ASGI_APPLICATION`` uses dots (``config.asgi.application``).
    Uvicorn and Granian use a colon (``config.asgi:application``).
    """
    if ":" in target:
        module_name, attr = target.split(":", 1)
    elif "." in target:
        module_name, attr = target.rsplit(".", 1)
    else:
        raise CommandError(f"Invalid ASGI target: {target!r}")
    if not module_name or not attr:
        raise CommandError(f"Invalid ASGI target: {target!r}")
    return module_name, attr


class _ServerNotAvailable(Exception):
    """Raised when an optional ASGI server package is not installed."""


class Command(BaseCommand):
    """Start Reflex dev (Vite + native Reflex backend). Django runs separately."""

    help = (
        "Run Reflex with frontend and Reflex backend (Django mounted in the "
        "Reflex backend). Set RX_PROXY_SERVER only when Django runs "
        "on a separate server."
    )

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
            help="Backend port when using --backend-only.",
        )
        parser.add_argument(
            "--backend-host",
            dest="backend_host",
            default=None,
            help="Backend bind host when using --backend-only.",
        )
        parser.add_argument(
            "--django-server",
            dest="django_server",
            default=None,
            help="Override RX_PROXY_SERVER for this run (e.g. http://127.0.0.1:8000).",
        )
        parser.add_argument(
            "--loglevel",
            choices=["debug", "info", "warning", "error", "critical"],
            default=None,
            help="Log level for the ASGI server when using --backend-only.",
        )
        parser.add_argument(
            "--frontend-only",
            action="store_true",
            help="Run only the Reflex frontend (Vite), not the Reflex backend.",
        )
        parser.add_argument(
            "--backend-only",
            action="store_true",
            help="Run only plain Django ASGI (no Vite).",
        )
        parser.add_argument(
            "--no-reload",
            action="store_true",
            dest="no_reload",
            help="Disable auto-reload on file changes.",
        )
        parser.add_argument(
            "--from-build",
            "--serve-build",
            action="store_true",
            dest="from_build",
            help="Export and serve the compiled SPA from Django instead of Vite HMR.",
        )
        parser.add_argument(
            "--with-vite",
            "--no-from-build",
            action="store_true",
            dest="with_vite",
            help="Force the Vite HMR dev loop when RX_SERVE_FROM_BUILD is set.",
        )
        parser.add_argument(
            "--skip-rebuild",
            action="store_true",
            dest="skip_rebuild",
            help="When --from-build is active, skip re-export before serving.",
        )
        parser.add_argument(
            "reflex_args",
            nargs="*",
            help="Additional arguments forwarded to ``reflex run`` (prefix with --).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from reflex_django.runtime.integration import (
            install_reflex_django_integration,
            refresh_get_config_bindings,
        )

        install_reflex_django_integration()
        refresh_get_config_bindings()

        if options.get("django_server"):
            os.environ["RX_PROXY_SERVER"] = str(options["django_server"]).strip()

        plan = build_run_plan(options)
        if plan.serve_from_disk:
            os.environ["RX_FRONTEND_PORT"] = str(plan.backend_port)
            os.environ["RX_BACKEND_PORT"] = str(plan.backend_port)
        else:
            os.environ.setdefault("RX_FRONTEND_PORT", str(plan.frontend_port))
            os.environ.setdefault("RX_BACKEND_PORT", str(plan.backend_port))
        os.environ.setdefault("RX_AUTO_EXPORT_ON_START", "0")

        if plan.serve_from_disk:
            os.environ["RX_DEV_PROXY"] = "0"
            os.environ["RX_SEPARATE_DEV_PORTS"] = "0"
        else:
            os.environ["RX_SEPARATE_DEV_PORTS"] = "1"
            os.environ["RX_DEV_PROXY"] = "0"

        if plan.is_prod:
            os.environ.setdefault("RX_DEBUG", "0")

        if plan.backend_only:
            self._run_plain_django(plan, options)
            return

        if plan.from_build and not plan.skip_rebuild:
            self._auto_export_for_build_mode(env=plan.env_name)

        if plan.from_build and plan.frontend_only:
            self.stdout.write(
                self.style.SUCCESS(
                    "reflex-django: export finished. Start Django with "
                    "`python manage.py run_reflex --backend-only` or "
                    "`python manage.py runserver`."
                )
            )
            return

        if plan.serve_from_disk:
            if plan.is_prod:
                self._warn_if_spa_missing()
            from reflex_django.mount.auto import refresh_reflex_mount_catchall

            refresh_reflex_mount_catchall()
            proxy_server = resolve_rxdjango_proxy_server()
            if proxy_server:
                django_note = (
                    f"Django admin/API proxied to {proxy_server} "
                    "(RX_PROXY_SERVER)."
                )
            else:
                django_note = (
                    "Django admin/API served from the Reflex backend "
                    "(set RX_PROXY_SERVER to proxy a separate Django server)."
                )
            mode = "prod" if plan.is_prod else "compiled bundle"
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"reflex-django: Reflex backend ({mode}, no Vite) — browse "
                    f"http://localhost:{plan.backend_port}/\n"
                    f"    {django_note}"
                )
            )
            # Plain Django ASGI cannot handle WebSocket /_event traffic.
            self._invoke_reflex_run(options, plan)
            return

        from reflex_django.dev.vite_proxy import ensure_vite_django_dev_proxy_from_config

        ensure_vite_django_dev_proxy_from_config()
        from reflex_django.mount.auto import refresh_reflex_mount_catchall

        refresh_reflex_mount_catchall()

        proxy_server = resolve_rxdjango_proxy_server()
        if proxy_server:
            django_note = (
                f"Django admin/API proxied to {proxy_server} "
                "(RX_PROXY_SERVER)."
            )
        else:
            django_note = (
                "Django admin/API served from the Reflex backend "
                "(set RX_PROXY_SERVER to proxy a separate Django server)."
            )
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "reflex-django: Reflex dev (Vite + Reflex backend) — browse "
                f"http://localhost:{plan.frontend_port}/\n"
                f"    {django_note}"
            )
        )

        self._invoke_reflex_run(options, plan)

    def _run_plain_django(self, plan: RunPlan, options: dict[str, Any]) -> None:
        """Serve Django HTTP only (``--backend-only``). No Reflex WebSocket events."""
        from django.conf import settings

        asgi_path = getattr(settings, "ASGI_APPLICATION", None)
        if not asgi_path or not isinstance(asgi_path, str):
            raise CommandError(
                "Set ASGI_APPLICATION in Django settings to run the Django backend."
            )

        reload = not options.get("no_reload") and not plan.is_prod
        self._run_asgi_server(
            target=asgi_path,
            host=plan.backend_host,
            port=plan.backend_port,
            loglevel=plan.loglevel,
            reload=reload,
        )

    def _auto_export_for_build_mode(self, env: str = "prod") -> None:
        from django.core.management import call_command
        from django.core.management.base import CommandError as DjangoCommandError

        try:
            from django.conf import settings

            has_static_root = bool(getattr(settings, "STATIC_ROOT", None))
        except Exception:
            has_static_root = False

        stage_to_static = env != "dev" and has_static_root
        self.stdout.write(
            self.style.NOTICE(
                f"reflex-django: auto-exporting Reflex SPA (env={env})..."
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
        except (DjangoCommandError, Exception) as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"reflex-django: auto-export failed: {exc}\n"
                    "    Falling back to any existing bundle on disk."
                )
            )
            return
        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: auto-export finished in {elapsed:.1f}s."
            )
        )

    def _warn_if_spa_missing(self) -> None:
        try:
            from reflex_django.mount.spa_paths import resolve_spa_index
        except Exception:
            return
        index = resolve_spa_index()
        if index is not None:
            self.stdout.write(
                self.style.SUCCESS(
                    f"reflex-django: found compiled SPA at {index}"
                )
            )
            return
        self.stdout.write(
            self.style.WARNING(
                "reflex-django: no compiled SPA found. Run:\n"
                "    python manage.py export_reflex --frontend-only --no-zip "
                "--stage-to-static-root"
            )
        )

    def _run_asgi_server(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
    ) -> None:
        for runner in (self._run_uvicorn, self._run_granian, self._run_hypercorn):
            try:
                runner(
                    target=target,
                    host=host,
                    port=port,
                    loglevel=loglevel,
                    reload=reload,
                )
                return
            except _ServerNotAvailable:
                continue

        raise CommandError(
            "Install uvicorn, granian, or hypercorn to serve Django ASGI."
        )

    def _run_uvicorn(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
    ) -> None:
        try:
            import uvicorn
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        module_name, attr = _parse_asgi_target(target)
        server_target = f"{module_name}:{attr}"
        application = getattr(importlib.import_module(module_name), attr)
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {server_target} via uvicorn at "
                f"http://{host}:{port}/"
            )
        )
        uvicorn.run(
            application,
            host=host,
            port=port,
            log_level=loglevel,
            reload=reload,
            ws="auto",
        )

    def _run_granian(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
    ) -> None:
        try:
            from granian.constants import Interfaces
            from granian.log import LogLevels
            from granian.server import Server as Granian
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        module_name, attr = _parse_asgi_target(target)
        server_target = f"{module_name}:{attr}"
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {server_target} via granian at "
                f"http://{host}:{port}/"
            )
        )
        Granian(
            server_target,
            address=host,
            port=port,
            interface=Interfaces.ASGI,
            log_level=LogLevels(loglevel),
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
    ) -> None:
        try:
            import asyncio

            from hypercorn.asyncio import serve
            from hypercorn.config import Config
        except ImportError as exc:
            raise _ServerNotAvailable from exc

        module_name, attr = _parse_asgi_target(target)
        server_target = f"{module_name}:{attr}"
        application = getattr(importlib.import_module(module_name), attr)
        cfg = Config()
        cfg.bind = [f"{host}:{port}"]
        cfg.loglevel = loglevel
        cfg.use_reloader = reload
        self.stdout.write(
            self.style.SUCCESS(
                f"reflex-django: serving {server_target} via hypercorn at "
                f"http://{host}:{port}/"
            )
        )
        asyncio.run(serve(application, cfg))

    def _invoke_reflex_run(self, options: dict[str, Any], plan: RunPlan) -> None:
        try:
            from reflex.reflex import cli as reflex_cli
        except ImportError as exc:
            raise CommandError(
                "Reflex is not installed in this environment."
            ) from exc

        if reflex_cli.commands.get("run") is None:
            raise CommandError("Reflex CLI has no 'run' command.")

        if options.get("no_reload"):
            os.environ["RX_BACKEND_RELOAD"] = "0"
        else:
            os.environ.pop("RX_BACKEND_RELOAD", None)

        import reflex_base.config as config_module
        from reflex_django.runtime.integration import _rebind_get_config_imports

        original_get_config = config_module.get_config
        frontend_only = bool(options.get("frontend_only"))
        single_port = plan.serve_from_disk

        def wrapped_get_config(reload: bool = False) -> Any:
            cfg = original_get_config(reload=reload)
            if frontend_only:
                cfg.backend_port = None
            elif single_port:
                port = plan.backend_port
                if getattr(cfg, "backend_port", None) is not None:
                    port = cfg.backend_port
                cfg.backend_port = port
                cfg.frontend_port = port
            return cfg

        config_module.get_config = wrapped_get_config
        _rebind_get_config_imports(wrapped_get_config)

        forward: list[str] = ["run"]
        if options.get("env"):
            forward.extend(["--env", options["env"]])
        if single_port:
            forward.extend(["--frontend-port", str(plan.backend_port)])
            forward.extend(["--backend-port", str(plan.backend_port)])
        else:
            if options.get("frontend_port"):
                forward.extend(["--frontend-port", str(options["frontend_port"])])
            if options.get("backend_port"):
                forward.extend(["--backend-port", str(options["backend_port"])])
        if options.get("backend_host"):
            forward.extend(["--backend-host", options["backend_host"]])
        if options.get("loglevel"):
            forward.extend(["--loglevel", options["loglevel"]])
        if frontend_only:
            forward.append("--frontend-only")
        forward.extend(options.get("reflex_args") or [])

        old_argv = sys.argv
        try:
            sys.argv = ["reflex", *forward]
            reflex_cli.main(standalone_mode=True)
        finally:
            sys.argv = old_argv
            config_module.get_config = original_get_config
            _rebind_get_config_imports(original_get_config)
