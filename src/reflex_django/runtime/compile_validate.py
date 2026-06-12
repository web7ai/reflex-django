"""Validate compiled frontend state dispatchers match the backend state tree."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.utils.console import Console

__all__ = [
    "ancestor_dispatch_keys_for_handler",
    "dispatch_keys_from_context_js",
    "expected_dispatch_keys_from_app",
    "filter_delta_to_compiled_dispatch_keys",
    "invalidate_stale_context_js",
    "missing_frontend_dispatchers",
    "warn_if_frontend_dispatchers_out_of_sync",
]


def ancestor_dispatch_keys_for_handler(handler_state_cls: type) -> set[str]:
    """Return full substate names on the root→handler path (for dispatch validation)."""
    import reflex as rx

    keys: set[str] = set()
    cls: type | None = handler_state_cls
    while cls is not None:
        if cls is rx.State or cls.__name__ == "State":
            break
        keys.add(cls.get_full_name())
        cls = cls.get_parent_state()
    return keys


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


def expected_dispatch_keys_from_app(app: Any | None = None) -> set[str]:
    """Return substate full names the live app expects in ``context.js`` dispatchers."""
    try:
        from reflex.compiler.utils import compile_state
        from reflex.state import State
    except ImportError:
        return set()

    if app is None:
        from reflex_django.runtime.app_factory import load_app_factory

        app = load_app_factory()

    state_cls = getattr(app, "_state", None) or getattr(app, "state", None) or State
    try:
        initial_state = compile_state(state_cls)
    except Exception:
        return set()
    return set(initial_state.keys())


def filter_delta_to_compiled_dispatch_keys(
    delta: dict[str, Any],
    *,
    app: Any | None = None,
    warn: bool = True,
) -> dict[str, Any]:
    """Drop delta entries for substates missing from the compiled frontend dispatch map."""
    if not delta:
        return delta

    allowed = expected_dispatch_keys_from_app(app)
    if not allowed:
        return delta

    filtered = {key: value for key, value in delta.items() if key in allowed}
    removed = sorted(set(delta) - set(filtered))
    if removed and warn:
        from reflex.utils import console

        console.warn(
            "reflex-django: omitted state delta for "
            f"{len(removed)} uncompiled substate(s): "
            + ", ".join(removed[:3])
            + (" …" if len(removed) > 3 else "")
            + ". Re-run `python manage.py run_reflex` from the project root and "
            "hard-refresh the browser (Ctrl+Shift+R)."
        )
    return filtered


def invalidate_stale_context_js(context_path: Path | None = None) -> bool:
    """Remove ``.web/utils/context.js`` so the next compile regenerates dispatchers."""
    path = context_path or _web_utils_context_path()
    if path is None or not path.is_file():
        return False
    path.unlink()
    return True


def missing_frontend_dispatchers(
    context_path: Path | None = None,
    *,
    expected_keys: set[str] | None = None,
    app: Any | None = None,
) -> list[str]:
    """Return app substate full names absent from the compiled dispatch map."""
    dispatch_keys = dispatch_keys_from_context_js(context_path)
    if not dispatch_keys:
        return []

    if expected_keys is None:
        expected_keys = expected_dispatch_keys_from_app(app)
    if not expected_keys:
        try:
            from reflex.state import all_base_state_classes
        except ImportError:
            return []
        expected_keys = set(all_base_state_classes)

    missing = sorted(expected_keys - dispatch_keys)
    return missing


def warn_if_frontend_dispatchers_out_of_sync(
    *,
    console: Console | None = None,
    context_path: Path | None = None,
    expected_keys: set[str] | None = None,
    app: Any | None = None,
) -> list[str]:
    """Warn when stale compile would cause ``dispatch is not a function`` in the browser."""
    missing = missing_frontend_dispatchers(
        context_path,
        expected_keys=expected_keys,
        app=app,
    )
    if not missing:
        return []

    if console is None:
        from reflex.utils import console as console_module

        console = console_module

    console.warn(
        "reflex-django: compiled frontend state dispatchers are missing "
        f"{len(missing)} app substate(s): "
        + ", ".join(missing[:5])
        + (" …" if len(missing) > 5 else "")
        + ". This causes 'dispatch is not a function' in the browser. "
        "Stop the dev server, run `python manage.py run_reflex` from the Django "
        "project root (so pages recompile), then hard-refresh http://localhost:3000/ "
        "(Ctrl+Shift+R). If the warning persists, delete `.web/` and run `run_reflex` again."
    )
    return missing
