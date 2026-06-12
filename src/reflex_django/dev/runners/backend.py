"""Internal uvicorn dev entry for reflex run with Django-outer backend reload."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="reflex_django.dev.runners.backend")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable uvicorn file watching.",
    )
    parser.set_defaults(reload=True)
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


def _backend_reload_enabled() -> bool:
    env = os.environ.get("REFLEX_DJANGO_BACKEND_RELOAD")
    if env is not None:
        return str(env).strip().lower() not in {"0", "false", "no"}
    return True


def main(argv: list[str] | None = None) -> int:
    args = _parse_argv(list(argv or sys.argv[1:]))

    from reflex_django.runtime.integration import install_reflex_django_integration

    install_reflex_django_integration()

    import uvicorn

    from reflex_django.dev.watch import BACKEND_RELOAD_DELAY_S, backend_reload_excludes

    reload = bool(args.reload) and _backend_reload_enabled()
    run_kwargs: dict[str, Any] = {
        "app": "reflex_django.asgi.entry:application",
        "factory": False,
        "host": args.host,
        "port": int(args.port),
        "log_level": args.log_level,
        "reload": reload,
        "ws": "auto",
    }
    if reload:
        run_kwargs["reload_dirs"] = [_resolve_watch_root()]
        run_kwargs["reload_delay"] = BACKEND_RELOAD_DELAY_S
        # ``reload_excludes`` globs hang uvicorn's reloader on Windows; match the
        # legacy ``run_reflex`` subprocess which only passed ``--reload-dir``.
        if (
            os.environ.get("REFLEX_DJANGO_FRONTEND_PRESENT") == "1"
            and sys.platform != "win32"
        ):
            run_kwargs["reload_excludes"] = backend_reload_excludes()

    uvicorn.run(**run_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
