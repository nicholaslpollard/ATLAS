"use strict";

[
  ["atlas-overview-style", "/assets/atlas_overview.css"],
  ["atlas-tabs-style", "/assets/atlas_tabs.css"],
  ["atlas-status-style", "/assets/atlas_status.css"],
].forEach(([key, href]) => {
  if (document.querySelector(`link[data-atlas-style="${key}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.dataset.atlasStyle = key;
  document.head.appendChild(link);
});

function atlasFinalizeSelectedBrandLayout() {
  document.querySelectorAll(".atlas-brand-name").forEach((node) => node.remove());

  const brand = document.querySelector(".atlas-brand");
  const mark = document.querySelector(".atlas-brand-mark");
  if (!brand || !mark) return;
  brand.classList.add("atlas-brand-selected");

  if (document.getElementById("atlas-selected-brand-layout-style")) return;
  const style = document.createElement("style");
  style.id = "atlas-selected-brand-layout-style";
  style.textContent = `
    .atlas-brand.atlas-brand-selected {
      min-height: 174px;
      padding: 0;
      gap: 0;
      display: grid;
      place-items: center;
    }
    .atlas-brand.atlas-brand-selected .atlas-brand-mark {
      width: 150px;
      height: 150px;
      margin: 0 auto;
      display: grid;
      place-items: center;
    }
    .atlas-brand.atlas-brand-selected .atlas-brand-mark > canvas,
    .atlas-brand.atlas-brand-selected .atlas-brand-mark > img,
    .atlas-brand.atlas-brand-selected .atlas-brand-mark > svg {
      display: block;
      width: 100%;
      height: 100%;
      margin: 0 auto;
      object-fit: contain;
    }
  `;
  document.head.appendChild(style);
}

window.addEventListener("DOMContentLoaded", () => {
  window.setTimeout(atlasFinalizeSelectedBrandLayout, 0);
  window.setTimeout(atlasFinalizeSelectedBrandLayout, 180);
});
window.addEventListener("atlas:observability-refreshed", atlasFinalizeSelectedBrandLayout);
