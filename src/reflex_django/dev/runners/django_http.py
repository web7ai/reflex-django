"""Internal uvicorn entry for the Django-only HTTP worker in REFLEX_OUTER mode."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="reflex_django.dev.runners.django_http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="warning",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable uvicorn file watching.",
    )
    parser.set_defaults(reload=False)
    return parser.parse_args(argv)


def _resolve_watch_root() -> str:
    try:
        from django.conf import settings

        base = getattr(settings, "BASE_DIR", None)
        if base:
            return str(base)
    except Exception:
        pass
    return str(os.getcwd())


def main(argv: list[str] | None = None) -> int:
    args = _parse_argv(list(argv or sys.argv[1:]))

    from reflex_django.setup.conf import configure_django

    configure_django()

    import uvicorn

    reload = bool(args.reload)
    run_kwargs: dict[str, Any] = {
        "app": "reflex_django.asgi.http_entry:application",
        "factory": False,
        "host": args.host,
        "port": int(args.port),
        "log_level": args.log_level,
        "reload": reload,
        "ws": "auto",
    }
    if reload:
        run_kwargs["reload_dirs"] = [_resolve_watch_root()]

    uvicorn.run(**run_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
