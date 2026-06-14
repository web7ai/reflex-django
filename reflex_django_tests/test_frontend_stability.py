"""Tests for EventLoopContext / React dedupe frontend patches."""

from __future__ import annotations

from pathlib import Path

from reflex_django.dev.frontend_stability import (
    apply_frontend_stability_after_compile,
    apply_frontend_stability_patches,
    patch_context_js,
    patch_default_overlay_components,
    patch_vite_react_dedupe,
    patch_vite_rollup_output,
)

_SAMPLE_CONTEXT = """import { createContext } from "react"
export const EventLoopContext = createContext(null);
export const DispatchContext = createContext(null);
"""

_SAMPLE_COMPONENT = """import { useContext } from "react"
import { EventLoopContext } from "$/utils/context"

export const Comp = () => {
    const [addEvents, connectErrors] = useContext(EventLoopContext);
    return null;
};
"""

_SAMPLE_VITE = """import { defineConfig } from "vite";

export default defineConfig({
  resolve: {
    mainFields: ["browser"],
    alias: [
      {
        find: "@",
        replacement: fileURLToPath(new URL("./public", import.meta.url)),
      },
    ],
  },
});
"""


def test_patch_context_js_replaces_null_default() -> None:
    out = patch_context_js(_SAMPLE_CONTEXT)
    assert "createContext([() => {}, []])" in out
    assert "EventLoopContext = createContext(null)" not in out


def test_patch_context_js_idempotent() -> None:
    once = patch_context_js(_SAMPLE_CONTEXT)
    assert patch_context_js(once) == once


def test_patch_default_overlay_components_replaces_destructure() -> None:
    out = patch_default_overlay_components(_SAMPLE_COMPONENT)
    assert "const eventLoop = useContext(EventLoopContext)" in out
    assert "const [addEvents, connectErrors]" not in out
    assert "Array.isArray(eventLoop)" in out


def test_patch_default_overlay_components_idempotent() -> None:
    once = patch_default_overlay_components(_SAMPLE_COMPONENT)
    assert patch_default_overlay_components(once) == once


_SAMPLE_VITE_ADVANCED_CHUNKS = """import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        advancedChunks: {
          groups: [
            {
              test: /env.json/,
              name: "reflex-env",
            },
          ],
        },
      },
    },
  },
});
"""


def test_patch_vite_rollup_output_replaces_advanced_chunks() -> None:
    out = patch_vite_rollup_output(_SAMPLE_VITE_ADVANCED_CHUNKS)
    assert "advancedChunks" not in out
    assert "manualChunks(id)" in out
    assert 'return "reflex-env"' in out


def test_patch_vite_react_dedupe_adds_dedupe_only() -> None:
    out = patch_vite_react_dedupe(_SAMPLE_VITE)
    assert 'dedupe: ["react", "react-dom", "@emotion/react"]' in out
    assert 'find: "react"' not in out


def test_patch_vite_react_dedupe_adds_minify_to_build() -> None:
    out = patch_vite_react_dedupe(_SAMPLE_VITE_ADVANCED_CHUNKS)
    assert 'minify: process.env.REFLEX_ENV_MODE !== "dev"' in out


def test_patch_vite_react_dedupe_strips_bad_react_aliases() -> None:
    broken = _SAMPLE_VITE.replace(
        'find: "@",',
        'find: "react",\n        replacement: fileURLToPath(new URL("./node_modules/react/index.js", import.meta.url)),\n      },\n      {\n        find: "@",',
    )
    out = patch_vite_react_dedupe(broken)
    assert "react/index.js" not in out
    assert 'dedupe: ["react", "react-dom", "@emotion/react"]' in out


def test_patch_vite_react_dedupe_idempotent() -> None:
    once = patch_vite_react_dedupe(_SAMPLE_VITE)
    assert patch_vite_react_dedupe(once) == once


def test_apply_frontend_stability_patches(tmp_path: Path) -> None:
    web = tmp_path / ".web"
    (web / "utils").mkdir(parents=True)
    (web / "utils" / "components").mkdir()
    (web / "app").mkdir()

    (web / "utils" / "context.js").write_text(_SAMPLE_CONTEXT, encoding="utf-8")
    (web / "utils" / "components" / "DefaultOverlayComponents.jsx").write_text(
        _SAMPLE_COMPONENT, encoding="utf-8"
    )
    (web / "utils" / "components" / "Button_x.jsx").write_text(
        _SAMPLE_COMPONENT, encoding="utf-8"
    )
    (web / "app" / "root.jsx").write_text(_SAMPLE_COMPONENT, encoding="utf-8")
    (web / "vite.config.js").write_text(_SAMPLE_VITE, encoding="utf-8")

    changed = [c.replace("\\", "/") for c in apply_frontend_stability_patches(web)]
    assert "utils/context.js" in changed
    assert "utils/components/DefaultOverlayComponents.jsx" in changed
    assert "utils/components/Button_x.jsx" in changed
    assert "app/root.jsx" in changed
    assert "vite.config.js" not in changed

    assert "createContext([() => {}, []])" in (web / "utils" / "context.js").read_text(
        encoding="utf-8"
    )
    assert "const eventLoop = useContext" in (
        web / "utils" / "components" / "Button_x.jsx"
    ).read_text(encoding="utf-8")

    assert apply_frontend_stability_patches(web) == []


def test_apply_frontend_stability_after_compile_uses_web_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    web = tmp_path / ".web"
    (web / "utils").mkdir(parents=True)
    (web / "utils" / "context.js").write_text(_SAMPLE_CONTEXT, encoding="utf-8")

    monkeypatch.setattr(
        "reflex.utils.prerequisites.get_web_dir",
        lambda: web,
    )

    changed = [c.replace("\\", "/") for c in apply_frontend_stability_after_compile()]
    assert "utils/context.js" in changed
    assert "createContext([() => {}, []])" in (web / "utils" / "context.js").read_text(
        encoding="utf-8"
    )
