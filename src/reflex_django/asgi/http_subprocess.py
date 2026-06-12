"""Spawn and manage the Django-only HTTP worker for REFLEX_OUTER mode."""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlsplit

from reflex_django.asgi.app import ASGIApp, ASGIReceive, ASGIScope, ASGISend
from reflex_django.core.env import truthy_env_or_none
from reflex_django.dev.process_utils import terminate_process

logger = logging.getLogger("reflex_django.asgi.http_subprocess")

_HTTP_UPSTREAM_ENV = "REFLEX_DJANGO_HTTP_UPSTREAM"
_HTTP_PORT_ENV = "REFLEX_DJANGO_HTTP_PORT"
_HTTP_SUBPROCESS_ENV = "REFLEX_DJANGO_HTTP_SUBPROCESS"
_HTTP_HOST_DEFAULT = "127.0.0.1"

_django_http_proc: subprocess.Popen[bytes] | None = None
_spawned_by_us = False


def _http_subprocess_enabled() -> bool:
    env = truthy_env_or_none(_HTTP_SUBPROCESS_ENV)
    if env is not None:
        return env
    try:
        from django.conf import settings

        return bool(getattr(settings, "REFLEX_DJANGO_HTTP_SUBPROCESS", True))
    except Exception:
        return True


def _resolve_http_port() -> int:
    env = os.environ.get(_HTTP_PORT_ENV)
    if env is not None and str(env).strip().isdigit():
        return int(str(env).strip())
    try:
        from django.conf import settings

        port = getattr(settings, "REFLEX_DJANGO_HTTP_PORT", 8001)
        return int(port)
    except Exception:
        return 8001


def pick_free_port(host: str = _HTTP_HOST_DEFAULT) -> int:
    """Return an ephemeral TCP port bound on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def resolve_django_http_upstream(*, port: int | None = None) -> str:
    """Return the Django HTTP upstream base URL."""
    env_upstream = os.environ.get(_HTTP_UPSTREAM_ENV, "").strip()
    if env_upstream:
        return env_upstream.rstrip("/")

    try:
        from django.conf import settings

        settings_upstream = str(
            getattr(settings, "REFLEX_DJANGO_HTTP_UPSTREAM", "") or ""
        ).strip()
        if settings_upstream:
            return settings_upstream.rstrip("/")
    except Exception:
        pass

    bind_port = port if port is not None else _resolve_http_port()
    host = os.environ.get("REFLEX_DJANGO_HTTP_HOST", _HTTP_HOST_DEFAULT)
    return f"http://{host}:{bind_port}"


def _tcp_reachable(upstream: str, timeout: float = 0.25) -> bool:
    parts = urlsplit(upstream)
    host = parts.hostname or _HTTP_HOST_DEFAULT
    port = parts.port
    if port is None:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_until_ready(
    upstream: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.1,
) -> bool:
    """Poll until the Django HTTP upstream accepts TCP connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _django_http_proc is not None and _django_http_proc.poll() is not None:
            logger.error(
                "Django HTTP subprocess exited before becoming ready (code=%s).",
                _django_http_proc.returncode,
            )
            return False
        if _tcp_reachable(upstream):
            return True
        time.sleep(interval)
    return False


def spawn_django_http_subprocess(
    *,
    port: int | None = None,
    host: str | None = None,
) -> subprocess.Popen[bytes]:
    """Start the Django-only HTTP worker in a child interpreter."""
    global _django_http_proc, _spawned_by_us

    if _django_http_proc is not None and _django_http_proc.poll() is None:
        return _django_http_proc

    bind_host = host or os.environ.get("REFLEX_DJANGO_HTTP_HOST", _HTTP_HOST_DEFAULT)
    bind_port = port if port is not None else _resolve_http_port()

    cmd = [
        sys.executable,
        "-m",
        "reflex_django.dev.runners.django_http",
        "--host",
        bind_host,
        "--port",
        str(bind_port),
        "--log-level",
        os.environ.get("REFLEX_DJANGO_HTTP_LOG_LEVEL", "warning"),
        "--no-reload",
    ]

    env = {**os.environ}
    upstream = f"http://{bind_host}:{bind_port}"
    env[_HTTP_UPSTREAM_ENV] = upstream

    logger.info(
        "reflex-django: starting Django HTTP subprocess at %s",
        upstream,
    )
    _django_http_proc = subprocess.Popen(cmd, env=env)
    _spawned_by_us = True
    os.environ[_HTTP_UPSTREAM_ENV] = upstream
    return _django_http_proc


def ensure_django_http_upstream_ready() -> str:
    """Ensure a reachable Django HTTP upstream exists; return its base URL."""
    upstream = resolve_django_http_upstream()

    if _tcp_reachable(upstream):
        return upstream

    if not _http_subprocess_enabled():
        msg = (
            f"reflex-django: Django HTTP upstream {upstream!r} is not reachable "
            f"and {_HTTP_SUBPROCESS_ENV} is disabled. Start a Django HTTP worker "
            "or set REFLEX_DJANGO_HTTP_UPSTREAM to a running server."
        )
        raise RuntimeError(msg)

    parts = urlsplit(upstream)
    port = parts.port or _resolve_http_port()
    host = parts.hostname or _HTTP_HOST_DEFAULT
    spawn_django_http_subprocess(port=port, host=host)

    upstream = resolve_django_http_upstream(port=port)
    if not wait_until_ready(upstream):
        terminate_django_http_subprocess()
        msg = (
            f"reflex-django: Django HTTP subprocess at {upstream!r} did not "
            "become ready in time."
        )
        raise RuntimeError(msg)

    return upstream


def terminate_django_http_subprocess() -> None:
    """Stop the Django HTTP subprocess if we spawned it."""
    global _django_http_proc, _spawned_by_us

    if _django_http_proc is None:
        return
    if not _spawned_by_us:
        _django_http_proc = None
        return

    proc = _django_http_proc
    _django_http_proc = None
    _spawned_by_us = False

    if proc.poll() is not None:
        return

    terminate_process(proc, timeout=5.0, use_sigint=False)


def wrap_reflex_asgi_with_django_http_lifecycle(inner: ASGIApp) -> ASGIApp:
    """Start/stop the Django HTTP worker around Reflex's ASGI lifespan."""
    from reflex_django.asgi.http_proxy import close_http_proxy_client
    from reflex_django.setup.routing import UrlRoutingMode, resolve_url_routing

    if resolve_url_routing() != UrlRoutingMode.REFLEX_OUTER:
        return inner

    async def outer(
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if scope.get("type") != "lifespan":
            await inner(scope, receive, send)
            return

        startup = await receive()
        if startup.get("type") != "lifespan.startup":
            return

        try:
            ensure_django_http_upstream_ready()
        except Exception as exc:
            logger.exception("Django HTTP subprocess startup failed")
            await send({"type": "lifespan.startup.failed", "message": repr(exc)})
            return

        startup_replayed = False

        async def replay_receive() -> Any:
            nonlocal startup_replayed
            if not startup_replayed:
                startup_replayed = True
                return startup
            return await receive()

        try:
            await inner(scope, replay_receive, send)
        finally:
            terminate_django_http_subprocess()
            await close_http_proxy_client()

    return outer


__all__ = [
    "ensure_django_http_upstream_ready",
    "pick_free_port",
    "resolve_django_http_upstream",
    "spawn_django_http_subprocess",
    "terminate_django_http_subprocess",
    "wait_until_ready",
    "wrap_reflex_asgi_with_django_http_lifecycle",
]