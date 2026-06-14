"""ASGI target parsing and Django ASGI server subprocess helpers."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from django.core.management.base import CommandError

if TYPE_CHECKING:
    from reflex_django.dev.run_plan import RunPlan
    from reflex_django.management.commands.run_reflex import Command


class _ServerNotAvailable(Exception):
    """Raised when an optional ASGI server package is not installed."""


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


def run_plain_django(command: Command, plan: RunPlan, options: dict[str, Any]) -> None:
    """Serve Django HTTP only (``--backend-only``). No Reflex WebSocket events."""
    from django.conf import settings

    asgi_path = getattr(settings, "ASGI_APPLICATION", None)
    if not asgi_path or not isinstance(asgi_path, str):
        raise CommandError(
            "Set ASGI_APPLICATION in Django settings to run the Django backend."
        )

    reload = not options.get("no_reload") and not plan.is_prod
    run_asgi_server(
        command,
        target=asgi_path,
        host=plan.backend_host,
        port=plan.backend_port,
        loglevel=plan.loglevel,
        reload=reload,
    )


def run_asgi_server(
    command: Command,
    *,
    target: str,
    host: str,
    port: int,
    loglevel: str,
    reload: bool,
) -> None:
    for runner in (run_uvicorn, run_granian, run_hypercorn):
        try:
            runner(
                command,
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


def run_uvicorn(
    command: Command,
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
    getattr(importlib.import_module(module_name), attr)
    command.stdout.write(
        command.style.SUCCESS(
            f"reflex-django: serving {server_target} via uvicorn at "
            f"http://{host}:{port}/"
        )
    )
    uvicorn_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "log_level": loglevel,
        "reload": reload,
        "ws": "auto",
    }
    if reload:
        from reflex_django.dev.watch import resolve_dev_watch_roots

        uvicorn_kwargs["reload_dirs"] = [
            str(path) for path in resolve_dev_watch_roots()
        ]
    uvicorn.run(server_target, **uvicorn_kwargs)


def run_granian(
    command: Command,
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
    command.stdout.write(
        command.style.SUCCESS(
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


def run_hypercorn(
    command: Command,
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
    command.stdout.write(
        command.style.SUCCESS(
            f"reflex-django: serving {server_target} via hypercorn at "
            f"http://{host}:{port}/"
        )
    )
    asyncio.run(serve(application, cfg))
