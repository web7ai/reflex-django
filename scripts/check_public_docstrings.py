"""Fail CI when public API symbols lack docstrings."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PUBLIC = [
    "configure_django",
    "create_app",
    "build_django_asgi",
    "DjangoEventBridge",
]


def main() -> int:
    import reflex_django

    missing: list[str] = []
    for name in PUBLIC:
        obj = getattr(reflex_django, name, None)
        if obj is None:
            continue
        if not (getattr(obj, "__doc__", None) or "").strip():
            missing.append(name)
    if missing:
        print("Missing docstrings:", ", ".join(missing))
        return 1
    print("Public API docstring check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())