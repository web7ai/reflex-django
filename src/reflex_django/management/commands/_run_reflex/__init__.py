"""Run Reflex dev (frontend + Reflex backend) via ``manage.py``.

Runs ``reflex run`` with the native Reflex backend and Vite. Django admin/API
paths are served from the Reflex backend by default. Set ``RX_PROXY_SERVER``
only when Django runs on a separate HTTP server.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from reflex_django.dev.run_plan import RunPlan, build_run_plan

from . import asgi_helpers
from .asgi_helpers import _parse_asgi_target
from .modes import backend_only, dev, from_build, frontend_only, prod

__all__ = ["Command", "_parse_asgi_target"]


def _apply_plan_env(plan: RunPlan) -> None:
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
            help="Run only Vite with frontend HMR (recompiles `.web` on Python edits).",
        )
        parser.add_argument(
            "--backend-only",
            action="store_true",
            help="Run only the Reflex backend (Django mounted, hot reload). No Vite.",
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
        _apply_plan_env(plan)

        if plan.backend_only:
            backend_only.run(self, options, plan)
            return

        if plan.frontend_only and not plan.from_build:
            frontend_only.run(self, options, plan)
            return

        if plan.from_build and not plan.skip_rebuild:
            from_build.auto_export_for_build_mode(self, env=plan.env_name)

        if plan.from_build and plan.frontend_only:
            from_build.write_export_finished_message(self)
            return

        if plan.serve_from_disk:
            if plan.is_prod:
                prod.run(self, options, plan)
            else:
                from_build.run_serve(self, options, plan)
            return

        dev.run(self, options, plan)

    def _run_plain_django(self, plan: RunPlan, options: dict[str, Any]) -> None:
        asgi_helpers.run_plain_django(self, plan, options)

    def _run_uvicorn(
        self,
        *,
        target: str,
        host: str,
        port: int,
        loglevel: str,
        reload: bool,
    ) -> None:
        asgi_helpers.run_uvicorn(
            self,
            target=target,
            host=host,
            port=port,
            loglevel=loglevel,
            reload=reload,
        )

    def _invoke_frontend_runner(
        self, options: dict[str, Any], plan: RunPlan
    ) -> None:
        """Run Vite and recompile ``.web`` when Reflex Python sources change."""
        from reflex_django.dev.runners import frontend as frontend_runner

        argv = ["--frontend-port", str(plan.frontend_port)]
        if options.get("no_reload"):
            argv.append("--no-watch")

        rc = frontend_runner.main(argv)
        if rc != 0:
            raise CommandError(f"Frontend dev server exited with code {rc}.")

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
        backend_only = bool(options.get("backend_only"))
        single_port = plan.serve_from_disk

        def wrapped_get_config(reload: bool = False) -> Any:
            cfg = original_get_config(reload=reload)
            if frontend_only:
                cfg.backend_port = None
            elif backend_only:
                cfg.frontend_port = None
                cfg.backend_port = plan.backend_port
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
        if backend_only:
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
