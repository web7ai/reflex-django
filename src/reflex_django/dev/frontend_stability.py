"""Post-compile patches for common Reflex + Vite dev issues.

Reflex generates ``EventLoopContext = createContext(null)`` and components that
destructure ``useContext(EventLoopContext)``. Before the provider mounts (or when
Vite loads duplicate React copies), that throws:

``TypeError: useContext is not a function or its return value is not iterable``

These patches run from :func:`apply_frontend_stability_after_compile` (after every
compile in dev/export) and from :func:`reflex_django.dev.vite_proxy.patch_vite_config`
(React dedupe only).

Documentation: https://web7ai.github.io/reflex-django/local_development/
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "apply_frontend_stability_after_compile",
    "apply_frontend_stability_patches",
    "patch_context_js",
    "patch_default_overlay_components",
    "patch_root_app_wrap",
    "patch_vite_react_dedupe",
    "patch_vite_rollup_output",
]


def patch_context_js(content: str) -> str:
    """Avoid destructuring null when EventLoopContext is read before the provider mounts."""
    updated = content.replace(
        "export const EventLoopContext = createContext(null);",
        "export const EventLoopContext = createContext([() => {}, []]);",
    )
    if updated == content:
        updated = re.sub(
            r"export const EventLoopContext = createContext\(\s*null\s*\);",
            "export const EventLoopContext = createContext([() => {}, []]);",
            content,
            count=1,
        )
    return updated


_EVENT_LOOP_DESTRUCTURE = re.compile(
    r"^(\s*)const \[addEvents, connectErrors\] = useContext\(EventLoopContext\);$",
    re.MULTILINE,
)
_EVENT_LOOP_SAFE = (
    r"\1const eventLoop = useContext(EventLoopContext);\n"
    r"\1const addEvents = Array.isArray(eventLoop) ? (eventLoop[0] ?? (() => {})) : (() => {});\n"
    r"\1const connectErrors = Array.isArray(eventLoop) ? (eventLoop[1] ?? []) : [];"
)


def patch_default_overlay_components(content: str) -> str:
    """Guard components when EventLoopContext is missing or not an array."""
    if "const eventLoop = useContext(EventLoopContext)" in content:
        return content
    return _EVENT_LOOP_DESTRUCTURE.sub(_EVENT_LOOP_SAFE, content)


def patch_root_app_wrap(content: str) -> str:
    """Same EventLoopContext guard for AppWrap in app/root.jsx."""
    return patch_default_overlay_components(content)


_REACT_INDEX_ALIAS = (
    "      {\n"
    '        find: "react",\n'
    '        replacement: fileURLToPath(new URL("./node_modules/react/index.js", import.meta.url)),\n'
    "      },\n"
)
_REACT_DOM_INDEX_ALIAS = (
    "      {\n"
    '        find: "react-dom",\n'
    '        replacement: fileURLToPath(new URL("./node_modules/react-dom/index.js", import.meta.url)),\n'
    "      },\n"
)


def strip_vite_react_file_aliases(content: str) -> str:
    """Remove react/index.js aliases that break ``react/jsx-runtime`` subpath imports."""
    updated = content.replace(_REACT_INDEX_ALIAS, "").replace(
        _REACT_DOM_INDEX_ALIAS, ""
    )
    return updated


_ADVANCED_CHUNKS_BLOCK = re.compile(
    r"""
    \s*output:\s*\{\s*
    advancedChunks:\s*\{\s*
    groups:\s*\[\s*
    \{\s*
    test:\s*/env\.json/,\s*
    name:\s*"reflex-env",\s*
    \},\s*
    \],\s*
    \},\s*
    \},\s*
    """,
    re.VERBOSE,
)

_MANUAL_CHUNKS_OUTPUT = """
      output: {
        manualChunks(id) {
          if (id && id.includes("env.json")) {
            return "reflex-env";
          }
        },
      },
"""


def patch_vite_rollup_output(content: str) -> str:
    """Replace Bun-only ``advancedChunks`` so Vite/Rollup SSR production builds succeed."""
    if "advancedChunks" not in content:
        return content
    updated, count = _ADVANCED_CHUNKS_BLOCK.subn(
        _MANUAL_CHUNKS_OUTPUT, content, count=1
    )
    return updated if count else content


def patch_vite_ssr_external(content: str) -> str:
    """Exclude pdfjs-dist from the prerender/SSR graph (needs DOMMatrix)."""
    if 'external: ["pdfjs-dist"]' in content or "external: ['pdfjs-dist']" in content:
        return content
    if "ssr:" in content:
        return content
    marker = re.search(r"\n\s*experimental\s*:\s*\{", content)
    if not marker:
        return content
    insert = "\n  ssr: {\n" '    external: ["pdfjs-dist"],\n' "  },"
    pos = marker.start()
    return content[:pos] + insert + content[pos:]


def patch_vite_strict_port(content: str) -> str:
    """Require Vite to bind the configured port (fail instead of auto-incrementing)."""
    if "strictPort" in content:
        return content
    match = re.search(r"server:\s*\{", content)
    if match is None:
        return content
    brace_pos = match.end() - 1
    newline = content.find("\n", brace_pos)
    insert_at = newline + 1 if newline != -1 else match.end()
    return content[:insert_at] + "\n    strictPort: true,\n" + content[insert_at:]


def patch_vite_react_dedupe(content: str) -> str:
    """Ensure a single React instance via Vite ``resolve.dedupe`` only.

    Do not alias ``react`` to ``react/index.js`` — that breaks subpaths like
    ``react/jsx-runtime`` (esbuild then looks for ``index.js/jsx-runtime``).
    """
    updated = patch_vite_rollup_output(content)
    updated = patch_vite_ssr_external(updated)
    updated = patch_vite_strict_port(updated)
    updated = strip_vite_react_file_aliases(updated)
    if not re.search(r"dedupe\s*:\s*\[", updated):
        match = re.search(r"(\n\s*resolve\s*:\s*\{)", updated)
        if match:
            insert = '\n    dedupe: ["react", "react-dom", "@emotion/react"],'
            pos = match.end()
            updated = updated[:pos] + insert + updated[pos:]
    if "minify:" not in updated:
        build_match = re.search(r"(build\s*:\s*\{)", updated)
        if build_match:
            pos = build_match.end()
            insert = '\n    minify: process.env.REFLEX_ENV_MODE !== "dev",'
            updated = updated[:pos] + insert + updated[pos:]
    return updated


def patch_all_event_loop_consumers(web_dir: Path) -> list[str]:
    """Patch every generated component that destructures EventLoopContext."""
    paths: list[Path] = []
    components_dir = web_dir / "utils" / "components"
    if components_dir.is_dir():
        paths.extend(components_dir.glob("*.jsx"))
    app_dir = web_dir / "app"
    if app_dir.is_dir():
        paths.extend(app_dir.rglob("*.jsx"))

    changed: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        old = path.read_text(encoding="utf-8")
        new = patch_default_overlay_components(old)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(web_dir)))
    return changed


def apply_frontend_stability_patches(web_dir: Path) -> list[str]:
    """Patch generated frontend files. Returns list of relative paths changed."""
    web_dir = Path(web_dir)
    changed: list[str] = []

    patches: list[tuple[Path, object]] = [
        (web_dir / "utils" / "context.js", patch_context_js),
        (
            web_dir / "utils" / "components" / "DefaultOverlayComponents.jsx",
            patch_default_overlay_components,
        ),
        (web_dir / "app" / "root.jsx", patch_root_app_wrap),
    ]

    for path, patch_fn in patches:
        if not path.is_file():
            continue
        old = path.read_text(encoding="utf-8")
        new = patch_fn(old)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(web_dir)))

    changed.extend(patch_all_event_loop_consumers(web_dir))

    return changed


def _log_stability_patches(changed: list[str]) -> None:
    if not changed:
        return
    from reflex.utils import console

    if len(changed) <= 5:
        detail = ", ".join(changed)
    else:
        detail = f"{len(changed)} files (e.g. {', '.join(changed[:3])}, …)"
    console.info("reflex-django applied frontend stability patches: " + detail)


def apply_frontend_stability_after_compile(web_dir: Path | None = None) -> list[str]:
    """Patch ``.web`` after Reflex compile (dev runner, export, or plugin hook).

    Call this whenever generated frontend files are written so EventLoopContext
    defaults and destructuring guards survive recompiles.
    """
    try:
        if web_dir is None:
            from reflex.utils import prerequisites

            web_dir = Path(prerequisites.get_web_dir())
        else:
            web_dir = Path(web_dir)
        if not web_dir.is_dir():
            return []
        changed = apply_frontend_stability_patches(web_dir)
        _log_stability_patches(changed)
        return changed
    except Exception as exc:
        from reflex.utils import console

        console.warn(
            "reflex-django could not apply frontend stability patches: " f"{exc}"
        )
        return []
