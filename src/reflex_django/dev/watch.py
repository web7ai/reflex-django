"""Classify dev file changes for frontend recompile vs backend reload.

``reflex run`` runs Vite (frontend HMR) and the Reflex backend side by side.
Without filtering, both watchers react to every ``.py`` save — e.g. editing
``settings.py`` would reload uvicorn *and* trigger a doomed SPA recompile.

These helpers split responsibilities:

- **Frontend recompile** — ``views.py``, layout/shell UI modules, global assets.
- **Backend reload** — state, settings, models, services, API routes, etc.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_UI_DIR_MARKERS: tuple[str, ...] = (
    f"{os.sep}shell{os.sep}",
    f"{os.sep}layout{os.sep}",
    f"{os.sep}components{os.sep}",
)

_BACKEND_SKIP_DIR_MARKERS: tuple[str, ...] = (
    f"{os.sep}migrations{os.sep}",
    f"{os.sep}tests{os.sep}",
    f"{os.sep}test_{os.sep}",
    f"{os.sep}.web{os.sep}",
    f"{os.sep}node_modules{os.sep}",
    f"{os.sep}staticfiles{os.sep}",
    f"{os.sep}static_collected{os.sep}",
)

# watchfiles debounce (ms) — lower = snappier reload after save.
WATCH_DEBOUNCE_MS = 200

# uvicorn ``reload_delay`` (seconds) before restarting the worker.
BACKEND_RELOAD_DELAY_S = 0.12


def resolve_dev_watch_roots() -> list[Path]:
    """Return Django project roots to watch for dev reload/recompile.

    Uses ``settings.BASE_DIR`` with ``Path.cwd()`` as fallback so host-project
    edits are detected even when Reflex ``config.module`` points at reflex-django.
    """
    roots: list[Path] = []

    try:
        from django.conf import settings

        base = getattr(settings, "BASE_DIR", None)
        if base:
            roots.append(Path(str(base)).resolve())
    except Exception:  # noqa: BLE001
        pass

    cwd = Path.cwd().resolve()
    if cwd not in roots:
        roots.append(cwd)

    return roots


def plugin_reload_paths() -> Sequence[Path]:
    """Return Reflex backend ``reload_dirs`` for plugin-integrated projects."""
    from reflex_base import constants
    from reflex_base.environment import environment

    include_dirs = tuple(
        map(Path.absolute, environment.REFLEX_HOT_RELOAD_INCLUDE_PATHS.get())
    )
    exclude_dirs = tuple(
        map(Path.absolute, environment.REFLEX_HOT_RELOAD_EXCLUDE_PATHS.get())
    )

    def is_excluded_by_default(path: Path) -> bool:
        if path.is_dir():
            if path.name.startswith("."):
                return True
            if path.name.startswith("__"):
                return True
        return path.name in (
            ".gitignore",
            "uploaded_files",
            constants.Bun.ROOT_LOCKFILE_DIR,
        )

    reload_paths: tuple[Path, ...] = (
        tuple(
            path.absolute()
            for root in resolve_dev_watch_roots()
            for path in root.iterdir()
            if not is_excluded_by_default(path)
        )
        + include_dirs
    )

    if exclude_dirs:
        reload_paths = tuple(
            path
            for path in reload_paths
            if all(not path.samefile(exclude) for exclude in exclude_dirs)
        )

    return reload_paths


def _norm_path(path: str) -> str:
    return os.path.normpath(path)


def is_frontend_recompile_path(path: str) -> bool:
    """Return True when *path* should trigger a Vite-side SPA recompile."""
    norm = _norm_path(path)
    if os.path.basename(norm) == "views.py":
        return True
    if any(marker in norm for marker in _UI_DIR_MARKERS):
        return True
    assets_marker = f"{os.sep}assets{os.sep}"
    if assets_marker in norm and norm.endswith((".css", ".js", ".jsx", ".tsx", ".mjs")):
        return True
    return False


def is_backend_reload_path(path: str) -> bool:
    """Return True when *path* should restart the ASGI backend in Vite dev mode."""
    norm = _norm_path(path)
    if not norm.endswith(".py"):
        return False
    if any(marker in norm for marker in _BACKEND_SKIP_DIR_MARKERS):
        return False
    if is_frontend_recompile_path(path):
        return False
    return True


def build_frontend_watch_filter(python_filter_cls: type) -> Any:
    """Return a watchfiles filter: SPA-relevant paths only."""

    class _FrontendRecompileFilter(python_filter_cls):  # type: ignore[misc, valid-type]
        def __call__(self, change, path: str) -> bool:  # noqa: D401, ANN001
            if not super().__call__(change, path):
                return False
            return is_frontend_recompile_path(path)

    return _FrontendRecompileFilter()


def build_backend_watch_filter(
    python_filter_cls: type,
    *,
    extra_excludes: list[str] | None = None,
) -> Any:
    """Return a watchfiles filter: backend-relevant ``.py`` paths only."""

    excludes = list(_BACKEND_SKIP_DIR_MARKERS)
    if extra_excludes:
        excludes.extend(extra_excludes)

    class _BackendReloadFilter(python_filter_cls):  # type: ignore[misc, valid-type]
        def __call__(self, change, path: str) -> bool:  # noqa: D401, ANN001
            if not super().__call__(change, path):
                return False
            norm = _norm_path(path)
            for needle in excludes:
                if needle in norm:
                    return False
            return is_backend_reload_path(path)

    return _BackendReloadFilter()


def backend_reload_excludes() -> list[str]:
    """Glob patterns for uvicorn ``reload_excludes`` (Vite dev, backend-only reload)."""
    return [
        "**/views.py",
        "**/shell/**",
        "**/layout/**",
        "**/components/**",
        "**/.web/**",
        "**/node_modules/**",
        "**/migrations/**",
        "**/tests/**",
        "**/test_*/**",
        "**/staticfiles/**",
        "**/static_collected/**",
        "**/__pycache__/**",
        "**/.git/**",
        "**/.venv/**",
        "**/venv/**",
    ]


__all__ = [
    "BACKEND_RELOAD_DELAY_S",
    "WATCH_DEBOUNCE_MS",
    "backend_reload_excludes",
    "build_backend_watch_filter",
    "build_frontend_watch_filter",
    "plugin_reload_paths",
    "is_backend_reload_path",
    "is_frontend_recompile_path",
    "resolve_dev_watch_roots",
]
