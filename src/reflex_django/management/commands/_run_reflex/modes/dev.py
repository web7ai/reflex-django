"""Default two-port Vite + Reflex backend dev mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_django.core.env import resolve_rxdjango_proxy_server
from reflex_django.dev.run_plan import RunPlan
from reflex_django.dev.vite_proxy import ensure_vite_django_dev_proxy_from_config
from reflex_django.mount.auto import refresh_reflex_mount_catchall

if TYPE_CHECKING:
    from reflex_django.management.commands.run_reflex import Command


def run(command: Command, options: dict[str, Any], plan: RunPlan) -> None:
    ensure_vite_django_dev_proxy_from_config()
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
            "reflex-django: Reflex dev (Vite + Reflex backend) — browse "
            f"http://localhost:{plan.frontend_port}/\n"
            f"    {django_note}"
        )
    )

    command._invoke_reflex_run(options, plan)
