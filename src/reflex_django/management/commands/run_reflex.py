"""Run the unified Reflex + Django dev server via ``manage.py``."""

from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Start Reflex and Django in one process (equivalent to ``reflex run``)."""

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
            help="Frontend port (Reflex dev server).",
        )
        parser.add_argument(
            "--backend-port",
            dest="backend_port",
            default=None,
            help="Backend port (ASGI).",
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
            help="Log level for Reflex.",
        )
        parser.add_argument(
            "--frontend-only",
            action="store_true",
            help="Run only the Reflex frontend.",
        )
        parser.add_argument(
            "--backend-only",
            action="store_true",
            help="Run only the Reflex backend.",
        )
        parser.add_argument(
            "reflex_args",
            nargs="*",
            help="Additional arguments forwarded to ``reflex run`` (prefix with --).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from reflex_django.integration import install_reflex_django_integration

        install_reflex_django_integration()

        try:
            from reflex.reflex import cli as reflex_cli
        except ImportError as exc:
            raise CommandError(
                "Reflex is not installed. Install reflex and reflex-django in this "
                "environment."
            ) from exc

        from reflex_django.integration import refresh_get_config_bindings

        refresh_get_config_bindings()

        if reflex_cli.commands.get("run") is None:
            raise CommandError("Reflex CLI has no 'run' command.")

        # Invoke the top-level ``reflex`` Click group (``reflex run ...``), not
        # ``run_cmd.main()`` — the subcommand parser rejects ``run`` as argv[1].
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
