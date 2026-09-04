"use strict";

function enforcePhase19SyntheticPreview() {
  if (document.getElementById("phase19-preview-banner")) return;
  const topbar = document.querySelector(".topbar");
  if (topbar) {
    const banner = document.createElement("section");
    banner.id = "phase19-preview-banner";
    banner.className = "banner warning";
    banner.setAttribute("role", "status");
    banner.textContent = "CODESPACES PREVIEW · SYNTHETIC DATA ONLY · no broker/provider connections · all POST requests disabled";
    topbar.insertAdjacentElement("afterend", banner);
  }

  const disableMutationControls = () => {
    document.querySelectorAll(".broker-actions button, #switch-confirm, #cleanup-confirm, .danger-action").forEach((button) => {
      button.disabled = true;
      button.title = "Disabled in synthetic Codespaces preview";
    });
  };

  disableMutationControls();
  const observer = new MutationObserver(disableMutationControls);
  observer.observe(document.body, { childList: true, subtree: true });

  const footer = document.querySelector("footer");
  if (footer) {
    footer.textContent = "ATLAS Codespaces synthetic preview · UI evaluation only · no market data, broker account, PAPER, LIVE, or research evidence is consumed";
  }
}

function finalizePreviewBrandLayout() {
  document.querySelectorAll(".atlas-brand-name").forEach((node) => node.remove());

  const brand = document.querySelector(".atlas-brand");
  const mark = document.querySelector(".atlas-brand-mark");
  if (!brand || !mark) return;
  brand.classList.add("atlas-brand-selected");

  if (document.getElementById("atlas-preview-brand-layout-style")) return;
  const style = document.createElement("style");
  style.id = "atlas-preview-brand-layout-style";
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
  enforcePhase19SyntheticPreview();
  window.setTimeout(finalizePreviewBrandLayout, 0);
  window.setTimeout(finalizePreviewBrandLayout, 180);
});
window.addEventListener("atlas:observability-refreshed", finalizePreviewBrandLayout);
