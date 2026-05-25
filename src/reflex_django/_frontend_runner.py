"""Internal entry point that compiles and runs the Vite dev server.

``manage.py run_reflex`` spawns this module as a subprocess when it needs to
launch the Vite dev server in :class:`~reflex_django.routing.UrlRoutingMode.DJANGO_OUTER`
mode. A fresh Python interpreter does not run reflex-django's import hooks
automatically — without ``install_reflex_django_integration()`` the Reflex
CLI fails with ``rxconfig.py not found`` (because our
:func:`~reflex_django.cli_layout.ensure_reflex_cli_layout` patch is not
installed).

We deliberately do not call ``reflex run --frontend-only`` here: Reflex's
``run`` command sets ``backend_port = backend_port or config.backend_port``
and then rejects the implicit value as ``Cannot specify --backend-port when
not running backend``. Instead we install the integration, compile the app,
and invoke ``reflex.utils.exec.run_frontend`` directly — same effect, no
spurious CLI validation.

Invoke as:

.. code-block:: bash

    python -m reflex_django._frontend_runner --frontend-port 3000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _parse_argv(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="reflex_django._frontend_runner")
    parser.add_argument(
        "--frontend-port",
        dest="frontend_port",
        type=int,
        default=None,
        help="Port the Vite dev server should listen on.",
    )
    parser.add_argument(
        "--frontend-host",
        dest="frontend_host",
        default="127.0.0.1",
        help="Bind host for the Vite dev server.",
    )
    # Tolerate extra args so callers can pass through unrelated options.
    args, _extras = parser.parse_known_args(argv)
    if args.frontend_port is not None:
        return int(args.frontend_port)
    env_port = os.environ.get("REFLEX_DJANGO_FRONTEND_PORT")
    if env_port and env_port.isdigit():
        return int(env_port)
    return 3000


def _bootstrap_integration() -> None:
    from reflex_django.conf import configure_django
    from reflex_django.integration import install_reflex_django_integration

    install_reflex_django_integration()
    try:
        from reflex_base.config import get_config

        get_config()
    except Exception:
        pass
    configure_django()


def _compile_app_for_frontend() -> None:
    """Run Reflex's compile step so ``.web`` is up to date before Vite starts."""
    from reflex.utils import prerequisites

    prerequisites.compile_or_validate_app(
        True,
        check_if_schema_up_to_date=True,
        prerender_routes=False,
    )


def _apply_persistent_frontend_port(port: int) -> None:
    """Push ``frontend_port`` into the active :class:`rx.Config` (mirrors reflex run)."""
    try:
        from reflex_base.config import get_config
    except Exception:
        return
    try:
        cfg = get_config()
        if hasattr(cfg, "_set_persistent"):
            cfg._set_persistent(frontend_port=port)
        elif hasattr(cfg, "frontend_port"):
            cfg.frontend_port = port
    except Exception:
        pass


def _run_vite(port: int) -> int:
    from reflex.utils import exec as reflex_exec

    root = Path.cwd()
    os.environ["PORT"] = str(port)
    reflex_exec.run_frontend(root, str(port), backend_present=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Bootstrap reflex-django, compile, and run Vite directly."""
    args = list(argv if argv is not None else sys.argv[1:])
    port = _parse_argv(args)

    _bootstrap_integration()
    _apply_persistent_frontend_port(port)

    try:
        _compile_app_for_frontend()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(
            f"reflex-django: frontend compile failed ({exc!r}). "
            "Vite will still start but pages may be missing.",
            file=sys.stderr,
        )

    try:
        return _run_vite(port)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
