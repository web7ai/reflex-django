"""Fail CI when docs text files are UTF-16 or contain embedded null bytes."""

from __future__ import annotations

import sys
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".txt", ".js", ".css"}


def is_corrupt(data: bytes) -> str | None:
    if data.startswith(b"\xff\xfe"):
        return "UTF-16 LE BOM"
    if data.startswith(b"\xfe\xff"):
        return "UTF-16 BE BOM"
    nulls = data.count(0)
    if nulls and nulls / max(len(data), 1) > 0.05:
        return f"{nulls} embedded null bytes"
    return None


def main() -> int:
    problems: list[str] = []
    for path in sorted(DOCS_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        reason = is_corrupt(path.read_bytes())
        if reason:
            problems.append(f"{path.relative_to(DOCS_ROOT)} ({reason})")

    if problems:
        print("Docs encoding check failed:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        print(
            "Re-save affected files as UTF-8 (no BOM). "
            "UTF-16 causes wide gaps in rendered code blocks.",
            file=sys.stderr,
        )
        return 1

    print("Docs encoding OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())