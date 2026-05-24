"""Prepare Reflex CLI layout for Django-first projects without ``reflex init``."""

from __future__ import annotations


def ensure_reflex_cli_layout() -> None:
    """Ensure ``rxconfig.py``, ``.reflex``, and ``.web`` exist for ``reflex run``.

    Django-first apps define pages in Django ``views.py`` and configure Reflex via
    ``reflex_mount()`` — they must not run :func:`reflex.reflex._init`, which scaffolds
    a blank app and prompts for templates.
    """
    from reflex_django.rxconfig_bridge import ensure_rxconfig_file

    ensure_rxconfig_file(for_cli=True)

    try:
        from reflex.utils import prerequisites
    except ImportError:
        return

    prerequisites.initialize_reflex_user_directory()
    prerequisites.ensure_reflex_installation_id()

    web_dir = prerequisites.get_web_dir()
    if not web_dir.exists():
        prerequisites.initialize_frontend_dependencies()
        return

    if not prerequisites._is_app_compiled_with_same_reflex_version():
        prerequisites.initialize_frontend_dependencies()
