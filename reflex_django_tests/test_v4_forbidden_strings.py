"""Guard against reintroducing removed django-first / v3 integration APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "reflex_django"

_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "IntegrationMode",
    "django_first_reload_paths",
    "install_reflex_first_integration",
    "install_django_first_integration",
    "get_or_create_app",
    "rxconfig_bridge",
    "register_mount_rx_config",
    "clear_mount_rx_config",
    "get_merged_mount_rx_config",
    "has_mount_rx_config",
    "reflex_django.runtime.reflex_app",
    "ensure_reflex_app_module_stub",
    "management.commands.run_reflex",
    "management.commands.export_reflex",
    "_bootstrap_reflex_integration_for_django",
    "register_mount_from_settings",
    "RX_CONFIG",
    "run_reflex",
    "export_reflex",
    "Backward-compat",
)


def _iter_source_files() -> list[Path]:
    return sorted(p for p in _SRC_ROOT.rglob("*.py") if p.is_file())


@pytest.mark.parametrize("needle", _FORBIDDEN_SUBSTRINGS)
def test_src_has_no_forbidden_v3_strings(needle: str) -> None:
    offenders: list[str] = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8")
        if needle in text:
            offenders.append(str(path.relative_to(_SRC_ROOT.parent)))
    assert not offenders, f"Forbidden substring {needle!r} found in: {offenders}"