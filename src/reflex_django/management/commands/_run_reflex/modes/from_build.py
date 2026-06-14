"""``--from-build`` export and compiled-bundle serving."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.dev.run_plan import RunPlan
from reflex_django.mount.auto import refresh_reflex_mount_catchall

if TYPE_CHECKING:
    from reflex_django.management.commands.run_reflex import Command


def auto_export_for_build_mode(command: Command, env: str = "prod") -> None:
    from django.core.management import call_command
    from django.core.management.base import CommandError as DjangoCommandError

    try:
        from django.conf import settings

        has_static_root = bool(getattr(settings, "STATIC_ROOT", None))
    except Exception:
        has_static_root = False

    stage_to_static = env != "dev" and has_static_root
    command.stdout.write(
        command.style.NOTICE(
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
        command.stdout.write(
            command.style.ERROR(
                f"reflex-django: auto-export failed: {exc}\n"
                "    Falling back to any existing bundle on disk."
            )
        )
        return
    elapsed = time.monotonic() - start
    command.stdout.write(
        command.style.SUCCESS(
            f"reflex-django: auto-export finished in {elapsed:.1f}s."
        )
    )


def write_export_finished_message(command: Command) -> None:
    command.stdout.write(
        command.style.SUCCESS(
            "reflex-django: export finished. Start Django with "
            "`python manage.py run_reflex --backend-only` or "
            "`python manage.py runserver`."
        )
    )


def run_serve(command: Command, options: dict[str, Any], plan: RunPlan) -> None:
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

    command.stdout.write(
        command.style.MIGRATE_HEADING(
            "reflex-django: Reflex backend (compiled bundle, no Vite) — browse "
            f"http://localhost:{plan.backend_port}/\n"
            f"    {django_note}"
        )
    )

    command._invoke_reflex_run(options, plan)
