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

window.addEventListener("DOMContentLoaded", enforcePhase19SyntheticPreview);
