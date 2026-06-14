#!/usr/bin/env python3
from __future__ import annotations
import os, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CANONICAL = {
    "learning_path.md": "getting-started/index.md",
    "mental_model.md": "overview/concepts.md",
    "why_reflex_django.md": "overview/concepts.md",
    "how_django_works.md": "overview/concepts.md",
    "how_reflex_works.md": "overview/concepts.md",
    "how_they_fit.md": "overview/concepts.md",
    "integration_guides.md": "getting-started/index.md",
    "installation.md": "getting-started/installation.md",
    "quickstart.md": "getting-started/quickstart.md",
    "local_development.md": "getting-started/local_development.md",
    "project_structure.md": "getting-started/project_structure.md",
    "configuration.md": "getting-started/configuration.md",
    "existing_django_project.md": "getting-started/existing_django_project.md",
    "existing_reflex_project.md": "getting-started/existing_reflex_project.md",
    "pages_in_views.md": "guides/pages.md",
    "state_management.md": "guides/state.md",
    "database_integration.md": "guides/database.md",
    "authentication.md": "guides/authentication.md",
    "django_middleware_to_reflex.md": "guides/middleware.md",
    "forms_and_validation.md": "guides/forms.md",
    "file_uploads.md": "guides/uploads.md",
    "media_files.md": "guides/media.md",
    "serializers.md": "guides/serializers.md",
    "reflex_django_mixins.md": "guides/mixins.md",
    "api_integration.md": "guides/api.md",
    "i18n.md": "guides/i18n.md",
    "cookbook.md": "guides/cookbook.md",
    "crud_without_mixins.md": "guides/crud.md#manual",
    "reactive_model_state.md": "guides/crud.md#modelstate",
    "crud_with_mixins_and_states.md": "guides/crud.md#modelcrudview",
    "model_state_and_crud_view.md": "guides/crud.md#choosing",
    "cli.md": "operations/cli.md",
    "testing.md": "operations/testing.md",
    "deployment.md": "operations/deployment.md",
    "scaling.md": "operations/scaling.md",
    "troubleshooting.md": "operations/troubleshooting.md",
    "best_practices.md": "operations/best_practices.md",
    "settings_reference.md": "reference/settings.md",
    "public_api.md": "reference/api.md",
    "faq.md": "reference/faq.md",
    "glossary.md": "reference/glossary.md",
    "architecture.md": "internals/architecture.md",
    "routing.md": "internals/routing.md",
    "websocket_event_pipeline.md": "internals/event_pipeline.md",
    "async_streaming_middleware.md": "internals/streaming_middleware.md",
}
LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)#]+)(#[^)]+)?(\))")

def normalize_target(raw):
    raw = raw.strip()
    if raw.startswith(("http://","https://","mailto:")) or raw.startswith("#"):
        return raw
    while raw.startswith("./"):
        raw = raw[2:]
    parts = []
    for seg in raw.split("/"):
        if seg == "..":
            if parts: parts.pop()
        elif seg and seg != ".":
            parts.append(seg)
    return "/".join(parts)

def rel_href(from_file, canonical):
    if "#" in canonical:
        path_part, frag = canonical.split("#", 1)
        frag_suffix = "#" + frag
    else:
        path_part, frag_suffix = canonical, ""
    from_dir = from_file.parent.relative_to(DOCS)
    rel = os.path.relpath(path_part, from_dir).replace("\\", "/")
    return rel + frag_suffix

def resolve_link(from_file, target):
    if target.startswith(("http://","https://","mailto:")) or target.startswith("#") or target.startswith("snippets/"):
        return None
    norm = normalize_target(target)
    base = norm.split("#")[0]
    frag = ("#" + norm.split("#",1)[1]) if "#" in norm else ""
    new = CANONICAL.get(base) or CANONICAL.get(base.split("/")[-1])
    if not new:
        return None
    if frag and "#" not in new:
        new += frag
    return rel_href(from_file, new)

def fix_file(path):
    text = path.read_text(encoding="utf-8")
    changes = 0
    def repl(m):
        nonlocal changes
        prefix, target, inline_frag, suffix = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        full = target + inline_frag
        new = resolve_link(path, full)
        if new and new != full:
            changes += 1
            return prefix + new + suffix
        return m.group(0)
    new_text = LINK_RE.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return changes

def main():
    total = 0
    for path in sorted(DOCS.rglob("*.md")):
        if "snippets" in path.parts or path.name == "STYLE.md":
            continue
        total += fix_file(path)
    for extra in (ROOT / "llm.txt", ROOT / "README.md"):
        if extra.exists():
            total += fix_file(extra)
    print(f"fix_doc_links: updated {total} link(s)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())