"""Validate compiled frontend state dispatchers match the backend state tree."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex.utils.console import Console

__all__ = [
    "dispatch_keys_from_context_js",
    "missing_frontend_dispatchers",
    "warn_if_frontend_dispatchers_out_of_sync",
]


def _web_utils_context_path() -> Path | None:
    try:
        from reflex_base.config import get_config
    except ImportError:
        return None
    try:
        config = get_config()
    except Exception:
        return None
    web_dir = getattr(config, "web_path", None) or getattr(config, "web_dir", None)
    if web_dir is None:
        return None
    path = Path(web_dir) / "utils" / "context.js"
    return path if path.is_file() else None


def dispatch_keys_from_context_js(context_path: Path | None = None) -> set[str]:
    """Parse dispatcher keys from ``.web/utils/context.js``."""
    path = context_path or _web_utils_context_path()
    if path is None:
        return set()
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'"([^"]+)":\s*dispatch_', text))


def missing_frontend_dispatchers(context_path: Path | None = None) -> list[str]:
    """Return backend state full names absent from the compiled dispatch map."""
    try:
        from reflex.state import all_base_state_classes
    except ImportError:
        return []

    dispatch_keys = dispatch_keys_from_context_js(context_path)
    if not dispatch_keys:
        return []

    missing = sorted(set(all_base_state_classes) - dispatch_keys)
    return missing


def warn_if_frontend_dispatchers_out_of_sync(
    *,
    console: Console | None = None,
    context_path: Path | None = None,
) -> list[str]:
    """Warn when stale compile would cause ``dispatch is not a function`` in the browser."""
    missing = missing_frontend_dispatchers(context_path)
    if not missing:
        return []

    if console is None:
        from reflex.utils import console as console_module

        console = console_module

    console.warn(
        "reflex-django: compiled frontend state dispatchers are missing "
        f"{len(missing)} backend substate(s): "
        + ", ".join(missing[:5])
        + (" …" if len(missing) > 5 else "")
        + ". This causes 'dispatch is not a function' in the browser. "
        "Stop the dev server, run `python manage.py run_reflex` from the Django "
        "project root (so pages recompile), then hard-refresh http://localhost:3000/ "
        "(Ctrl+Shift+R)."
    )
    return missing
