"""Prepare Reflex CLI layout for Django-first projects without ``reflex init``."""

from __future__ import annotations


def ensure_reflex_cli_layout() -> None:
    """Prepare Reflex CLI layout for Django-first projects (no ``rxconfig.py`` on disk).

    Live ``rx.Config`` comes from ``reflex_mount()`` via an in-memory ``rxconfig``
    module. Creates ``.reflex`` / ``.web`` when missing; does not run
    :func:`reflex.reflex._init` or write ``rxconfig.py``.
    """
    from reflex_django.mount.config import ensure_mount_config_loaded
    from reflex_django.setup.rxconfig_bridge import (
        ensure_rxconfig_from_django,
        remove_django_first_rxconfig_stub,
    )

    ensure_mount_config_loaded()
    ensure_rxconfig_from_django()
    remove_django_first_rxconfig_stub()

    try:
        from reflex.utils import prerequisites
    except ImportError:
        return

    prerequisites.initialize_reflex_user_directory()
    prerequisites.ensure_reflex_installation_id()

    web_dir = prerequisites.get_web_dir()
    try:
        from django.conf import settings
        is_debug = settings.DEBUG
    except Exception:
        is_debug = True

    if not is_debug:
        import sys
        args = [arg.lower() for arg in sys.argv]
        is_build = any(
            x in args
            for x in ("export", "export_reflex", "deploy", "build", "compile")
        )
        if not is_build:
            return

    if not web_dir.exists():
        prerequisites.initialize_frontend_dependencies()
        return

    if not prerequisites._is_app_compiled_with_same_reflex_version():
        prerequisites.initialize_frontend_dependencies()

