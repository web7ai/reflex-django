"""Reflex-version compatibility guardrails.

These smoke tests fail loudly when a Reflex upgrade renames or removes any
private symbol reflex-django monkeypatches, instead of breaking silently at
runtime.
"""

from __future__ import annotations

import pytest

from reflex_django.core.compat import (
    PATCHED_SYMBOLS,
    SUPPORTED_REFLEX_SPECIFIER,
    check_patch_targets,
    installed_reflex_version,
    reflex_version_supported,
)


def test_all_patched_symbols_exist() -> None:
    missing = check_patch_targets(include_optional=False)
    assert missing == [], "Patched Reflex internals missing: " + "; ".join(missing)


@pytest.mark.parametrize("target", PATCHED_SYMBOLS, ids=lambda t: t.dotted)
def test_each_required_patch_target_resolves(target) -> None:
    if target.optional:
        pytest.skip(f"{target.dotted} is optional")
    assert target.resolve_error() is None


def test_supported_specifier_is_declared() -> None:
    assert SUPPORTED_REFLEX_SPECIFIER == ">=0.9.4,<1.0"


def test_installed_reflex_within_supported_range() -> None:
    version = installed_reflex_version()
    assert version is not None
    assert reflex_version_supported(
        version
    ), f"Installed Reflex {version} is outside {SUPPORTED_REFLEX_SPECIFIER}"


def test_reflex_version_supported_boundaries() -> None:
    assert reflex_version_supported("0.9.4") is True
    assert reflex_version_supported("0.9.10") is True
    assert reflex_version_supported("0.9.3") is False
    assert reflex_version_supported("1.0.0") is False
    assert reflex_version_supported("0.12.0") is True
    # Unknown version must not block.
    assert reflex_version_supported(None) is True
    assert reflex_version_supported("") is True


def test_dotted_names_are_unique_and_descriptive() -> None:
    dotted = [t.dotted for t in PATCHED_SYMBOLS]
    assert len(dotted) == len(set(dotted))
    assert all("." in name for name in dotted)
