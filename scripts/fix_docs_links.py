from pathlib import Path
import re

SECTION_ROOTS = frozenset({"advanced", "learn"})
LINK_RE = re.compile(r"\]\(([^)]+)\)")
DOCS = Path(r"c:\Users\mohan\PycharmProjects\reflex_django\reflex-django\docs")


def fix_target(target):
    if "://" in target or target.startswith("mailto:"):
        return target
    anchor = ""
    path = target
    if "#" in path:
        path, frag = path.split("#", 1)
        anchor = f"#{frag}"
    if not path.endswith("/"):
        return target
    stem = path.rstrip("/")
    basename = stem.rsplit("/", 1)[-1]
    if basename in SECTION_ROOTS:
        return f"{stem}/index.md{anchor}"
    return f"{stem}.md{anchor}"


total = 0
for path in sorted(DOCS.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    changes = []

    def repl(m):
        orig = m.group(1)
        fixed = fix_target(orig)
        if fixed != orig:
            changes.append((orig, fixed))
        return f"]({fixed})"

    updated = LINK_RE.sub(repl, text)
    if changes:
        path.write_text(updated, encoding="utf-8")
        print(f"{path.name}: {len(changes)} links")
        total += len(changes)
print(f"Fixed {total} links")
