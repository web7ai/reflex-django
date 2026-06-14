"""``--env prod`` compiled SPA serving."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.dev.run_plan import RunPlan
from reflex_django.mount.auto import refresh_reflex_mount_catchall

if TYPE_CHECKING:
    from reflex_django.management.commands.run_reflex import Command


def warn_if_spa_missing(command: Command) -> None:
    try:
        from reflex_django.mount.spa_paths import resolve_spa_index
    except Exception:
        return
    index = resolve_spa_index()
    if index is not None:
        command.stdout.write(
            command.style.SUCCESS(
                f"reflex-django: found compiled SPA at {index}"
            )
        )
        return
    command.stdout.write(
        command.style.WARNING(
            "reflex-django: no compiled SPA found. Run:\n"
            "    python manage.py export_reflex --frontend-only --no-zip "
            "--stage-to-static-root"
        )
    )


def run(command: Command, options: dict[str, Any], plan: RunPlan) -> None:
    warn_if_spa_missing(command)
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
            "reflex-django: Reflex backend (prod, no Vite) — browse "
            f"http://localhost:{plan.backend_port}/\n"
            f"    {django_note}"
        )
    )

    command._invoke_reflex_run(options, plan)
