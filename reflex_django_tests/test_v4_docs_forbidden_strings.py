"""Guard against reintroducing v3 workflow strings in user-facing docs."""

from __future__ import annotations

from pathlib import Path

import pytest

_DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"

_FORBIDDEN: tuple[str, ...] = (
    "manage.py run_reflex",
    "manage.py export_reflex",
    "from reflex_django import app",
    "IntegrationMode",
    "RX_PLUGINS",
    "reflex_django.runtime.reflex_app",
    "get_or_create_app",
    "install_reflex_django_integration",
    "install_django_first_integration",
    "Django-first config",
)

_ALLOWED_PATH_FRAGMENTS: tuple[str, ...] = (
    "reference/migration/v4_plugin_only.md",
    "getting-started/existing_reflex_project.md",
    "getting-started/configuration.md",
    "getting-started/existing_django_project.md",
)


def _iter_doc_files() -> list[Path]:
    files: list[Path] = []
    for path in _DOCS_ROOT.rglob("*.md"):
        if not path.is_file():
            continue
        if "_archive" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def _is_allowed(path: Path) -> bool:
    rel = path.relative_to(_DOCS_ROOT).as_posix()
    return any(fragment in rel for fragment in _ALLOWED_PATH_FRAGMENTS)


@pytest.mark.parametrize("needle", _FORBIDDEN)
def test_docs_avoid_forbidden_v3_workflow_strings(needle: str) -> None:
    offenders: list[str] = []
    for path in _iter_doc_files():
        if _is_allowed(path):
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            offenders.append(path.relative_to(_DOCS_ROOT).as_posix())
    assert not offenders, f"{needle!r} found in: {offenders}"


@pytest.mark.parametrize("path", _iter_doc_files())
def test_docs_are_utf8(path: Path) -> None:
    raw = path.read_bytes()
    nulls = sum(1 for b in raw if b == 0)
    assert nulls == 0, f"{path} has {nulls} null bytes (UTF-16?)"
