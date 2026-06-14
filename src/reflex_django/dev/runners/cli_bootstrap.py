"""Site path hook: register ``django`` on Reflex's CLI when appropriate.

A ``.pth`` file in the wheel installs this module so it is imported very early
during interpreter startup (see :pep:`420` path configuration). We only attach
commands when the process looks like the Reflex CLI, to avoid importing Reflex
for unrelated ``python`` invocations.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ATTACHED = False


def _argv_looks_like_reflex_cli() -> bool:
    argv = sys.argv
    if not argv:
        return False
    prog = Path(argv[0]).name.lower().removesuffix(".exe")
    if prog == "reflex":
        return True
    if len(argv) >= 3 and argv[1] == "-m" and argv[2] == "reflex":
        return True
    return False


def _attach() -> None:
    global _ATTACHED
    if _ATTACHED:
        return
    if not _argv_looks_like_reflex_cli():
        return
    try:
        import reflex.reflex as _rr
    except ImportError:
        return
    from reflex_django.cli import register_django_cli_group_if_needed

    register_django_cli_group_if_needed(_rr.cli)
    try:
        from reflex_django.runtime.integration.registry import install_early_cli_patch

        install_early_cli_patch()
    except Exception:
        pass
    _ATTACHED = True


_attach()
