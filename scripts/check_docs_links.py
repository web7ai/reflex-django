"""Fail CI when docs use trailing-slash internal markdown links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def is_bad_target(target: str) -> bool:
    if "://" in target or target.startswith("mailto:"):
        return False
    path = target.split("#", 1)[0]
    return path.endswith("/")


def main() -> int:
    problems: list[str] = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        if "_archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if is_bad_target(target):
                rel = path.relative_to(DOCS_ROOT)
                problems.append(f"{rel}: ]({target})")

    if problems:
        print("Docs link check failed:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        print(
            "Use .md paths for internal links (e.g. learn/integration.md).",
            file=sys.stderr,
        )
        return 1

    print("Docs links OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
