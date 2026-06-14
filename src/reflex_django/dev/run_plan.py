"""Resolve dev-server flags into a single RunPlan dataclass."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from reflex_django.core.constants import DEFAULT_BACKEND_PORT, DEFAULT_FRONTEND_PORT
from reflex_django.core.env import setting_or_env_bool
from reflex_django.core.constants import ENV_SERVE_FROM_BUILD

ReloadStrategy = Literal["parent_watch", "uvicorn_reload", "none"]


@dataclass(frozen=True)
class RunPlan:
    env_name: str
    is_prod: bool
    from_build: bool
    serve_from_disk: bool
    is_single_port_dev: bool
    frontend_only: bool
    backend_only: bool
    skip_rebuild: bool
    with_vite: bool
    backend_host: str
    backend_port: int
    frontend_port: int
    loglevel: str


def resolve_from_build(options: dict[str, Any]) -> bool:
    """Resolve serve-from-disk flag using documented precedence."""
    with_vite = bool(options.get("with_vite"))
    explicit_from_build = bool(options.get("from_build"))
    is_env_dev = options.get("env") == "dev"
    is_prod = (options.get("env") or "dev") == "prod"
    if is_prod:
        return True
    if is_env_dev:
        return False
    if with_vite and not explicit_from_build:
        return False
    if explicit_from_build:
        return True
    return setting_or_env_bool(ENV_SERVE_FROM_BUILD, "RX_SERVE_FROM_BUILD", default=False)


def build_run_plan(options: dict[str, Any]) -> RunPlan:
    """Build a RunPlan from manage.py command options."""
    env_name = options.get("env") or "dev"
    is_prod = env_name == "prod"
    with_vite = bool(options.get("with_vite"))
    is_env_dev = options.get("env") == "dev"
    from_build = resolve_from_build(options)
    serve_from_disk = is_prod or from_build
    backend_port = int(
        options.get("backend_port")
        or os.environ.get("RX_BACKEND_PORT")
        or DEFAULT_BACKEND_PORT
    )
    frontend_port = int(
        options.get("frontend_port")
        or os.environ.get("RX_FRONTEND_PORT")
        or DEFAULT_FRONTEND_PORT
    )
    if serve_from_disk:
        frontend_port = backend_port
    return RunPlan(
        env_name=env_name,
        is_prod=is_prod,
        from_build=from_build,
        serve_from_disk=serve_from_disk,
        is_single_port_dev=False,
        frontend_only=bool(options.get("frontend_only")),
        backend_only=bool(options.get("backend_only")),
        skip_rebuild=bool(options.get("skip_rebuild")),
        with_vite=with_vite,
        backend_host=str(
            options.get("backend_host")
            or os.environ.get("RX_BACKEND_HOST")
            or "0.0.0.0"
        ),
        backend_port=backend_port,
        frontend_port=frontend_port,
        loglevel=str(options.get("loglevel") or "info"),
    )


__all__ = ["ReloadStrategy", "RunPlan", "build_run_plan", "resolve_from_build"]