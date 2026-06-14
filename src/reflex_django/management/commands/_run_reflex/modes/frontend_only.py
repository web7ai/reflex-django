"""``--frontend-only`` run mode."""

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
        backend_note = (
            f"Backend proxied to {proxy_server} (RX_PROXY_SERVER)."
        )
    else:
        backend_note = (
            f"Pair with `--backend-only` on :{plan.backend_port} "
            "for the Reflex backend + Django."
        )

    command.stdout.write(
        command.style.MIGRATE_HEADING(
            "reflex-django: Vite frontend only — browse "
            f"http://localhost:{plan.frontend_port}/\n"
            f"    {backend_note}\n"
            "    Python edits recompile `.web` automatically (frontend HMR)."
        )
    )

    command._invoke_frontend_runner(options, plan)
