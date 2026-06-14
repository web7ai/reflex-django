#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {"_archive", ".venv", "site", "__pycache__", ".git"}
REPLACEMENTS = [
    ("REFLEX_DJANGO_RX_CONFIG", "RX_CONFIG"),
    ("REFLEX_DJANGO_HTTP_UPSTREAM", "RX_PROXY_SERVER"),
    ("REFLEX_DJANGO_", "RX_"),
    ("RXDJANGO_PROXY_SERVER", "RX_PROXY_SERVER"),
    ("_reflex_django_bridge", "_rx_bridge"),
    ('"reflex_django_bridge"', '"rx_bridge"'),
    ("'reflex_django_bridge'", "'rx_bridge'"),
    ("rxdj:event:", "rx:event:"),
]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".rst"}


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("utf-8")


def should_process(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.name == "rename_rx_settings.py":
        return False
    return path.suffix.lower() in TEXT_SUFFIXES


def transform(text: str) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    return text


def main() -> None:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_process(path):
            continue
        try:
            original = read_text(path)
        except UnicodeDecodeError:
            print(f"SKIP decode error: {path}")
            continue
        updated = transform(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    print(f"Updated {changed} files")


if __name__ == "__main__":
    main()
