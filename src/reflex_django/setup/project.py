"""Project layout helpers: ``manage.py`` discovery and ``rxconfig.py`` paths."""

from __future__ import annotations

import ast
import sys
from importlib.util import find_spec
from pathlib import Path

_RXCONFIG_MODULE = "rxconfig"
_RXCONFIG_FILE = "rxconfig.py"
RXCONFIG_SYNTHETIC_ATTR = "__reflex_django_synthetic__"


def find_manage_py(start: Path | None = None) -> Path | None:
    """Walk parents from *start* (or cwd) looking for ``manage.py``.

    Returns:
        Path to the nearest ``manage.py``, or ``None``.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / "manage.py"
        if candidate.is_file():
            return candidate
    return None


def ensure_django_project_on_path(start: Path | None = None) -> Path | None:
    """Insert the nearest ``manage.py`` parent directory onto ``sys.path``.

    ``reflex run`` does not add the Django project root to ``PYTHONPATH`` the way
    ``manage.py`` does. Required before importing ``demo.settings`` and similar
    layout modules created by ``django-admin startproject``.
    """
    manage_py = find_manage_py(start)
    if manage_py is None:
        return None
    root = str(manage_py.parent.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    return manage_py.parent


def parse_settings_module(manage_py: Path) -> str | None:
    """AST-parse ``DJANGO_SETTINGS_MODULE`` from a standard ``manage.py``.

    Supports ``os.environ.setdefault(...)`` and ``os.environ[...] = ...``.

    Returns:
        Dotted settings module path, or ``None`` if not found statically.
    """
    try:
        source = manage_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(manage_py))
    except (OSError, SyntaxError):
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "setdefault":
            if (
                isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "os"
                and len(node.args) >= 2
                and _is_settings_module_key(node.args[0])
            ):
                value = _literal_str(node.args[1])
                if value:
                    return value

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not _is_settings_module_subscript(target):
                continue
            value = _literal_str(node.value)
            if value:
                return value
    return None


def _is_settings_module_key(node: ast.expr) -> bool:
    return _literal_str(node) == "DJANGO_SETTINGS_MODULE"


def _is_settings_module_subscript(node: ast.Subscript) -> bool:
    if isinstance(node.slice, ast.Constant):
        return node.slice.value == "DJANGO_SETTINGS_MODULE"
    return False


def _literal_str(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def discover_settings_module(start: Path | None = None) -> str | None:
    """Return the settings module declared in the nearest ``manage.py``."""
    manage_py = find_manage_py(start)
    if manage_py is None:
        return None
    return parse_settings_module(manage_py)


def rxconfig_path(start: Path | None = None) -> Path | None:
    """Return the project-root ``rxconfig.py`` if it exists."""
    manage_py = find_manage_py(start)
    root = manage_py.parent if manage_py is not None else (start or Path.cwd())
    candidate = root.resolve() / _RXCONFIG_FILE
    return candidate if candidate.is_file() else None


def rxconfig_module_has_file() -> bool:
    """Return whether ``rxconfig`` is backed by a real on-disk module (not synthetic).

    On Python 3.14+, :func:`importlib.util.find_spec` raises :class:`ValueError` when
    ``rxconfig`` is in ``sys.modules`` without a loader spec.
    """
    if rxconfig_path() is not None:
        return True
    mod = sys.modules.get(_RXCONFIG_MODULE)
    if mod is not None:
        if getattr(mod, RXCONFIG_SYNTHETIC_ATTR, False):
            return False
        return bool(getattr(mod, "__file__", None))
    try:
        spec = find_spec(_RXCONFIG_MODULE)
    except (ValueError, ModuleNotFoundError):
        return False
    if spec is None:
        return False
    return spec.origin not in (None, "namespace")
