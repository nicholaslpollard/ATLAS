"use strict";

// Late-created panels can be inserted inside an already-routed page. Treat a direct
// child of any atlas-page as a movable top-level block, not the page itself.
function atlasTopMainChild(node) {
  const main = document.querySelector("main");
  let current = node;
  while (current && current.parentElement) {
    const parent = current.parentElement;
    if (parent === main || parent.classList.contains("atlas-page")) break;
    if (parent.id === "atlas-page-host") break;
    current = parent;
  }
  return current;
}

function atlasMoveAnchor(anchorId, pageId, includeHeader = false) {
  const anchor = document.getElementById(anchorId);
  const page = atlasPage(pageId);
  if (!anchor || !page) return;
  const top = atlasTopMainChild(anchor);
  if (!top || top.classList.contains("atlas-page") || top.parentElement === page) return;
  if (includeHeader) {
    const previous = top.previousElementSibling;
    if (previous && previous.classList.contains("section-head")) page.appendChild(previous);
  }
  page.appendChild(top);
}

function atlasRuntimeCosmetics() {
  const safety = document.getElementById("safety-banner");
  const preview = Boolean(safety && /CODESPACES PREVIEW|SYNTHETIC/i.test(safety.textContent || ""));
  document.body.classList.toggle("atlas-preview-mode", preview);
  const context = document.querySelector(".atlas-clock-session");
  if (context) context.textContent = preview ? "SYNTHETIC PREVIEW" : "LOCAL CONSOLE";

  const refresh = document.getElementById("local-observability-interval");
  if (refresh) {
    const seconds = Number(refresh.value || 0);
    atlasSet("atlas-ctl-refresh", seconds > 0 ? `${seconds}s LOCAL` : "MANUAL / LOCAL");
  }
}

const atlasRuntimeStyle = document.createElement("style");
atlasRuntimeStyle.textContent = `
  body.atlas-console-active > main > #safety-banner { display: none; }
  body.atlas-console-active.atlas-preview-mode > main > #safety-banner {
    display: block;
    position: fixed;
    z-index: 58;
    left: var(--atlas-sidebar);
    right: 0;
    top: var(--atlas-topbar);
    margin: 0;
    min-height: 28px;
    padding: 6px 18px;
    border-radius: 0;
    border-left: 0;
    border-right: 0;
    background: rgba(112, 77, 0, .94);
    color: #ffd86a;
    font-size: 10px;
    letter-spacing: .08em;
    text-align: center;
  }
  body.atlas-console-active.atlas-preview-mode .atlas-console-main { padding-top: 50px !important; }
`;
document.head.appendChild(atlasRuntimeStyle);

window.addEventListener("atlas:observability-refreshed", () => {
  window.setTimeout(() => {
    atlasRouteSections();
    atlasRuntimeCosmetics();
  }, 80);
});

window.addEventListener("DOMContentLoaded", () => {
  window.setTimeout(atlasRuntimeCosmetics, 120);
  window.setTimeout(atlasRuntimeCosmetics, 500);
  window.setInterval(() => {
    if (!document.hidden) atlasRuntimeCosmetics();
  }, 1000);
});
