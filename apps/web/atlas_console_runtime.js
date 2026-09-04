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

const atlasSelectedBrandPngBase64 = "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";

async function atlasRenderSelectedBrand() {
  const host = document.querySelector(".atlas-brand-mark");
  if (!host || host.dataset.atlasBrandAsset === "selected") return;

  try {
    const binary = atob(atlasSelectedBrandPngBase64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/png" }));
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.setAttribute("aria-label", "ATLAS");
    canvas.setAttribute("role", "img");
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0);
    if (typeof bitmap.close === "function") bitmap.close();
    host.replaceChildren(canvas);
    host.dataset.atlasBrandAsset = "selected";
  } catch (_error) {
    // Keep the inline SVG fallback if browser bitmap decoding is unavailable.
  }
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
  void atlasRenderSelectedBrand();
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

  .atlas-brand { min-height: 164px; gap: 0; }
  .atlas-brand-mark {
    width: 132px;
    height: 132px;
    filter: drop-shadow(0 0 13px rgba(16, 199, 255, .28));
  }
  .atlas-brand-mark canvas {
    display: block;
    width: 100%;
    height: 100%;
  }
  .atlas-brand-name { display: none; }
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
