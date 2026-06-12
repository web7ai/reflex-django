#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EM_DASH = "\u2014"
DEPRECATED_TERMS = ("django_led_app", "ReflexDjangoPlugin")
MIGRATION_ALLOWLIST = {
    "migration/v1_migration.md",
    "migration/v2_module_paths.md",
    "migration/v0-to-v1.md",
    "migration_django_outer.md",
    "whats_new.md",
    "faq.md",
    "glossary.md",
    "public_api.md",
    "websocket_event_pipeline.md",
    "architecture.md",
}


def iter_markdown_files():
    return [
        p
        for p in sorted(DOCS.rglob("*.md"))
        if p.name != "STYLE.md" and "snippets" not in p.parts
    ]


def check_learning_path_hrefs(path: Path, text: str) -> list[str]:
    issues: list[str] = []
    if path.name != "learning_path.md":
        return issues
    for i, line in enumerate(text.splitlines(), 1):
        if "rd-path-card" not in line or 'href="' not in line:
            continue
        match = re.search(r'href="([^"]+)"', line)
        if match and not match.group(1).startswith("../"):
            issues.append(
                f"{path.relative_to(ROOT)}:{i}: path card href must use ../ prefix ({match.group(1)!r})"
            )
    return issues


def main():
    errors: list[str] = []
    warnings: list[str] = []
    for path in iter_markdown_files():
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(DOCS)).replace("\\", "/")
        for i, line in enumerate(text.splitlines(), 1):
            if EM_DASH in line:
                errors.append(f"{path.relative_to(ROOT)}:{i}: em dash")
        errors.extend(check_learning_path_hrefs(path, text))
        if rel not in MIGRATION_ALLOWLIST:
            for term in DEPRECATED_TERMS:
                if term in text:
                    warnings.append(f"{path.relative_to(ROOT)}: deprecated {term!r}")
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"check_docs_style: OK ({len(iter_markdown_files())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())