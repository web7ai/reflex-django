"""Reflex-version compatibility guardrails.

reflex-django monkeypatches a number of private Reflex / reflex-base / component
internals (see :data:`PATCHED_SYMBOLS`). A Reflex upgrade can rename or remove
any of these, silently breaking the integration. This module centralizes:

- the supported Reflex version range (mirrors ``pyproject.toml``), and
- a smoke check (:func:`check_patch_targets`) asserting every patched symbol
  still exists, used by the test suite and surfaced as a startup warning.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

# Keep in sync with the ``reflex`` pin in ``pyproject.toml``.
MIN_REFLEX_VERSION = (0, 9, 4)
MAX_REFLEX_VERSION_EXCLUSIVE = (1, 0, 0)
SUPPORTED_REFLEX_SPECIFIER = ">=0.9.4,<1.0"


@dataclass(frozen=True)
class PatchTarget:
    """A symbol reflex-django monkeypatches and therefore depends on."""

    module: str
    attr: str
    child: str | None = None
    note: str = ""
    optional: bool = False

    @property
    def dotted(self) -> str:
        base = f"{self.module}.{self.attr}"
        return f"{base}.{self.child}" if self.child else base

    def resolve_error(self) -> str | None:
        """Return an error string if the symbol is missing, else ``None``."""
        try:
            module = importlib.import_module(self.module)
        except Exception as exc:  # pragma: no cover - import errors are rare
            return f"cannot import {self.module!r}: {exc!r}"
        obj = getattr(module, self.attr, _MISSING)
        if obj is _MISSING:
            return f"{self.module!r} has no attribute {self.attr!r}"
        if self.child is not None and not hasattr(obj, self.child):
            return f"{self.module}.{self.attr} has no attribute {self.child!r}"
        return None


_MISSING = object()


# Every Reflex/reflex-base/component symbol reflex-django patches or binds to.
PATCHED_SYMBOLS: tuple[PatchTarget, ...] = (
    PatchTarget(
        "reflex_base.event.processor.base_state_processor",
        "process_event",
        note="bridge binds the Django request before each event",
    ),
    PatchTarget(
        "reflex_base.event.context",
        "EventContext",
        "emit_delta",
        note="filters deltas to compiled dispatch keys",
    ),
    PatchTarget(
        "reflex.utils.frontend_skeleton",
        "_compile_vite_config",
        note="injects Django dev proxy rules into vite.config.js",
    ),
    PatchTarget(
        "reflex.app",
        "App",
        "_compile",
        note="re-applies Vite proxy after compile",
    ),
    PatchTarget(
        "reflex.app",
        "App",
        "_apply_decorated_pages",
        note="buckets decorated pages under the mount app_name",
    ),
    PatchTarget(
        "reflex.reflex",
        "_compile_app",
        note="in-process compile + dispatcher sync",
    ),
    PatchTarget(
        "reflex.page",
        "page",
        note="Django-first @page registration",
    ),
    PatchTarget(
        "reflex.page",
        "DECORATED_PAGES",
        note="decorated-page registry buckets",
    ),
    PatchTarget(
        "reflex.state",
        "BaseState",
        "__getstate__",
        note="strips Django request artefacts before pickling",
    ),
    PatchTarget(
        "reflex_components_core.core._upload",
        "_upload_buffered_file",
        note="injects router_data into upload events",
    ),
    PatchTarget(
        "reflex_components_core.core._upload",
        "_upload_chunk_file",
        note="injects router_data into chunked upload events",
    ),
    PatchTarget(
        "reflex.state",
        "StateProxy",
        note="unwrapped during request binding",
        optional=True,
    ),
)


def check_patch_targets(
    *,
    include_optional: bool = False,
) -> list[str]:
    """Return human-readable errors for any missing patch targets.

    Args:
        include_optional: When ``True``, optional targets are also checked.
    """
    errors: list[str] = []
    for target in PATCHED_SYMBOLS:
        if target.optional and not include_optional:
            continue
        error = target.resolve_error()
        if error is not None:
            errors.append(f"{target.dotted}: {error}")
    return errors


def installed_reflex_version() -> str | None:
    """Return the installed Reflex version string, or ``None`` if unknown."""
    try:
        from importlib.metadata import version

        return version("reflex")
    except Exception:
        try:
            import reflex

            return getattr(reflex, "__version__", None)
        except Exception:
            return None


def _parse_version(value: str) -> tuple[int, int, int]:
    parts: list[int] = []
    for chunk in value.split(".")[:3]:
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def reflex_version_supported(version: str | None = None) -> bool:
    """Return whether *version* (default: installed) is within the supported range."""
    resolved = version if version is not None else installed_reflex_version()
    if not resolved:
        return True  # unknown: do not block
    parsed = _parse_version(resolved)
    return MIN_REFLEX_VERSION <= parsed < MAX_REFLEX_VERSION_EXCLUSIVE


def warn_if_unsupported_reflex() -> None:
    """Emit a console warning if Reflex is outside the supported range or patches drift."""
    version = installed_reflex_version()
    if version is not None and not reflex_version_supported(version):
        try:
            from reflex_base.utils import console

            console.warn(
                f"reflex-django supports Reflex {SUPPORTED_REFLEX_SPECIFIER}, but "
                f"{version} is installed. Patched internals may have changed."
            )
        except Exception:
            pass

    missing = check_patch_targets()
    if missing:
        try:
            from reflex_base.utils import console

            console.warn(
                "reflex-django could not find expected Reflex internals: "
                + "; ".join(missing)
            )
        except Exception:
            pass


__all__ = [
    "MAX_REFLEX_VERSION_EXCLUSIVE",
    "MIN_REFLEX_VERSION",
    "PATCHED_SYMBOLS",
    "PatchTarget",
    "SUPPORTED_REFLEX_SPECIFIER",
    "check_patch_targets",
    "installed_reflex_version",
    "reflex_version_supported",
    "warn_if_unsupported_reflex",
]
