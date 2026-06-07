"""ASGI server runners for manage.py run_reflex."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any


class ServerNotAvailable(Exception):
    """Raised when no ASGI server package is installed."""


def run_asgi_server(
    *,
    target: str,
    host: str,
    port: int,
    loglevel: str,
    reload: bool,
    reload_backend_only: bool,
) -> None:
    for runner in (_run_uvicorn, _run_granian, _run_hypercorn):
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
        except ServerNotAvailable:
            continue
    msg = "No ASGI server found. Install uvicorn, granian, or hypercorn."
    raise ServerNotAvailable(msg)


def _run_uvicorn(**kwargs: Any) -> None:
    import uvicorn
    uvicorn.run(
        kwargs["target"],
        host=kwargs["host"],
        port=kwargs["port"],
        log_level=kwargs["loglevel"],
        reload=kwargs["reload"],
        reload_dirs=None if kwargs["reload_backend_only"] else None,
    )


def _run_granian(**kwargs: Any) -> None:
    try:
        from granian import Granian
    except ImportError as exc:
        raise ServerNotAvailable from exc
    Granian(
        kwargs["target"],
        address=kwargs["host"],
        port=kwargs["port"],
        interface="asgi",
        reload=kwargs["reload"],
    ).serve()


def _run_hypercorn(**kwargs: Any) -> None:
    try:
        from hypercorn.config import Config
        from hypercorn.asyncio import serve
    except ImportError as exc:
        raise ServerNotAvailable from exc
    import asyncio
    config = Config()
    config.bind = [f"{kwargs['host']}:{kwargs['port']}"]
    asyncio.run(serve(kwargs["target"], config))


def build_uvicorn_cmd(
    *,
    target: str,
    host: str,
    port: int,
    loglevel: str,
    reload: bool = False,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        target,
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        loglevel,
    ]
    if reload:
        cmd.append("--reload")
    return cmd


def spawn_uvicorn_subprocess(
    *,
    target: str,
    host: str,
    port: int,
    loglevel: str,
    reload: bool,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    env = {**os.environ, **(extra_env or {})}
    return subprocess.Popen(build_uvicorn_cmd(
        target=target, host=host, port=port, loglevel=loglevel, reload=reload
    ), env=env)


__all__ = ["ServerNotAvailable", "build_uvicorn_cmd", "run_asgi_server", "spawn_uvicorn_subprocess"]