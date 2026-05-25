// Mermaid initialization for Material for MkDocs.
//
// We render Mermaid manually so we can:
//   1) Pick a theme that matches the pink reflex-django palette.
//   2) Re-render diagrams on every page navigation, including the
//      navigation.instant feature which doesn't fully reload the page.
//   3) Re-render on light/dark theme toggle.

(function () {
  if (typeof window === "undefined") return;

  function pickTheme() {
    var scheme =
      document.body.getAttribute("data-md-color-scheme") || "default";
    return scheme === "slate" ? "dark" : "default";
  }

  function themeVariables() {
    var isDark =
      document.body.getAttribute("data-md-color-scheme") === "slate";
    if (isDark) {
      return {
        background: "#15151a",
        primaryColor: "#1d1f27",
        primaryTextColor: "#f8bbd0",
        primaryBorderColor: "#f48fb1",
        lineColor: "#f48fb1",
        secondaryColor: "#25272f",
        tertiaryColor: "#1a1a20",
        nodeBorder: "#f48fb1",
        clusterBkg: "#1a1a20",
        clusterBorder: "#f48fb1",
        edgeLabelBackground: "#1d1f27",
        fontFamily: "Inter, system-ui, sans-serif",
      };
    }
    return {
      background: "#fffafc",
      primaryColor: "#fff0f5",
      primaryTextColor: "#880e4f",
      primaryBorderColor: "#e91e63",
      lineColor: "#c2185b",
      secondaryColor: "#fce4ec",
      tertiaryColor: "#fff5f8",
      nodeBorder: "#e91e63",
      clusterBkg: "#fff5f8",
      clusterBorder: "#f06292",
      edgeLabelBackground: "#fff0f5",
      fontFamily: "Inter, system-ui, sans-serif",
    };
  }

  function configure() {
    if (!window.mermaid) return false;
    window.mermaid.initialize({
      startOnLoad: false,
      theme: pickTheme(),
      themeVariables: themeVariables(),
      flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis" },
      sequence: { useMaxWidth: true },
      securityLevel: "loose",
    });
    return true;
  }

  function renderAll() {
    if (!configure()) return;
    var nodes = document.querySelectorAll("pre.mermaid, .mermaid");
    if (!nodes.length) return;

    nodes.forEach(function (node) {
      // Material wraps the source in <pre class="mermaid"><code>...</code></pre>.
      // Mermaid needs the raw graph text directly inside <div class="mermaid">,
      // so the first time we see a <pre>, we extract the code, replace the
      // <pre> with a fresh <div class="mermaid">, and mark it for processing.
      if (
        node.tagName === "PRE" &&
        !node.hasAttribute("data-rd-mermaid-converted")
      ) {
        var code = node.querySelector("code");
        var source = (code ? code.textContent : node.textContent) || "";
        var div = document.createElement("div");
        div.className = "mermaid";
        div.textContent = source;
        div.setAttribute("data-rd-mermaid-converted", "true");
        node.parentNode.replaceChild(div, node);
      } else if (
        node.tagName !== "PRE" &&
        !node.hasAttribute("data-rd-mermaid-converted")
      ) {
        node.setAttribute("data-rd-mermaid-converted", "true");
      }
    });

    // mermaid.run() picks up every element with .mermaid that hasn't been
    // processed yet (Mermaid stamps them with data-processed="true").
    try {
      window.mermaid.run({
        querySelector: ".mermaid:not([data-processed='true'])",
      });
    } catch (err) {
      console.error("Mermaid render failed:", err);
    }
  }

  function waitForMermaid(retriesLeft) {
    if (window.mermaid) {
      renderAll();
      return;
    }
    if (retriesLeft <= 0) return;
    setTimeout(function () {
      waitForMermaid(retriesLeft - 1);
    }, 100);
  }

  function boot() {
    waitForMermaid(50);
  }

  // First load.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // Material's navigation.instant emits this when a new page is swapped in.
  if (typeof document$ !== "undefined" && document$.subscribe) {
    document$.subscribe(function () {
      // Reset processed flag on diagrams that were re-inserted by navigation.
      document
        .querySelectorAll(".mermaid[data-processed]")
        .forEach(function (el) {
          // Already rendered, leave it.
        });
      boot();
    });
  }

  // Re-render when the user toggles light/dark mode.
  var paletteObserver = new MutationObserver(function (mutations) {
    for (var m of mutations) {
      if (m.attributeName === "data-md-color-scheme") {
        // Remove cached SVGs so they pick up the new theme.
        document
          .querySelectorAll(".mermaid[data-processed]")
          .forEach(function (el) {
            var src = el.getAttribute("data-rd-source");
            if (src) {
              el.removeAttribute("data-processed");
              el.innerHTML = src;
            }
          });
        boot();
        break;
      }
    }
  });

  if (document.body) {
    // Cache raw sources before Mermaid replaces them with SVG, so we can
    // re-render after a theme toggle.
    document.querySelectorAll(".mermaid").forEach(function (el) {
      if (!el.getAttribute("data-rd-source")) {
        el.setAttribute("data-rd-source", el.textContent);
      }
    });
    paletteObserver.observe(document.body, { attributes: true });
  }
})();
