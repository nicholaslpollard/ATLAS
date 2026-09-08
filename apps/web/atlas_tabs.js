"use strict";

const atlasDomainTabs = {
  market: [
    ["candidates", "Candidates", ["candidate-date-summary", "candidate-search"]],
    ["live", "Live Data", ["live-market-panel", "live-quotes-table"]],
  ],
  research: [
    ["strategies", "Strategies & Replay", ["reference-lab-banner", "reference-lab-strategy-body", "reference-lab-equity-chart", "reference-lab-decisions-body"]],
    ["ai", "AI Review", ["ai-date"]],
  ],
  portfolio: [
    ["account", "Account & Positions", ["paper-state", "paper-positions-table"]],
    ["health", "Evidence Health", ["paper-health-list"]],
  ],
  execution: [
    ["lifecycle", "Decision & Order Lifecycle", ["paper-decisions-table"]],
    ["outcomes", "Outcomes", ["paper-closed-table", "outcome-count", "outcomes-table"]],
  ],
  brokers: [
    ["accounts", "Broker Accounts", ["brokers"]],
    ["inputs", "Market Inputs", ["phase19-readiness-controls"]],
  ],
  operations: [
    ["pipeline", "Pipeline", ["pipeline-stages"]],
    ["actions", "Actions", ["actions-table"]],
    ["lineage", "Lineage", ["lineage-merge"]],
  ],
};

const atlasDomainTabState = {};

function atlasDomainTopBlock(anchor) {
  if (!anchor) return null;
  const page = anchor.closest(".atlas-page");
  if (!page) return null;
  let node = anchor;
  while (node.parentElement && node.parentElement !== page) node = node.parentElement;
  return node.parentElement === page ? node : null;
}

function atlasDomainAddBlock(set, block) {
  if (!block || block.classList.contains("atlas-page-heading") || block.classList.contains("atlas-domain-tabs")) return;
  set.add(block);
  const previous = block.previousElementSibling;
  if (previous && previous.classList.contains("section-head")) set.add(previous);
}

function atlasEnsureDomainTabs(pageId) {
  const definitions = atlasDomainTabs[pageId];
  const page = atlasPage(pageId);
  if (!definitions || !page) return null;
  let nav = page.querySelector(":scope > .atlas-domain-tabs");
  if (nav) return nav;

  nav = atlasEl("nav", "atlas-domain-tabs");
  nav.setAttribute("aria-label", `${pageId} sections`);
  const heading = page.querySelector(":scope > .atlas-page-heading");
  definitions.forEach(([tabId, label]) => {
    const button = atlasEl("button", "atlas-domain-tab", label);
    button.type = "button";
    button.dataset.domainPage = pageId;
    button.dataset.domainTab = tabId;
    button.addEventListener("click", () => atlasSetDomainTab(pageId, tabId));
    nav.appendChild(button);
  });
  if (heading) heading.insertAdjacentElement("afterend", nav);
  else page.insertAdjacentElement("afterbegin", nav);
  return nav;
}

function atlasSetDomainTab(pageId, tabId) {
  const definitions = atlasDomainTabs[pageId];
  if (!definitions || !definitions.some(([id]) => id === tabId)) return;
  atlasDomainTabState[pageId] = tabId;
  atlasApplyDomainTabs(pageId);
}

function atlasApplyDomainTabs(pageId) {
  const definitions = atlasDomainTabs[pageId];
  const page = atlasPage(pageId);
  if (!definitions || !page) return;
  const nav = atlasEnsureDomainTabs(pageId);
  const active = atlasDomainTabState[pageId] || definitions[0][0];
  atlasDomainTabState[pageId] = active;

  const tabBlocks = new Map();
  definitions.forEach(([tabId, , anchors]) => {
    const blocks = new Set();
    anchors.forEach((anchorId) => {
      const anchor = document.getElementById(anchorId);
      const block = atlasDomainTopBlock(anchor);
      atlasDomainAddBlock(blocks, block);
    });
    tabBlocks.set(tabId, blocks);
  });

  const allManaged = new Set();
  tabBlocks.forEach((blocks) => blocks.forEach((block) => allManaged.add(block)));
  allManaged.forEach((block) => {
    let owner = null;
    for (const [tabId, blocks] of tabBlocks.entries()) {
      if (blocks.has(block)) {
        owner = tabId;
        break;
      }
    }
    block.hidden = owner !== active;
    block.dataset.atlasDomainTab = owner || "";
  });

  nav?.querySelectorAll(".atlas-domain-tab").forEach((button) => {
    const selected = button.dataset.domainTab === active;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  });
}

function atlasRefreshDomainTabs() {
  Object.keys(atlasDomainTabs).forEach((pageId) => atlasApplyDomainTabs(pageId));
}

window.addEventListener("atlas:observability-refreshed", () => {
  window.setTimeout(atlasRefreshDomainTabs, 160);
});

window.addEventListener("DOMContentLoaded", () => {
  window.setTimeout(atlasRefreshDomainTabs, 140);
  window.setTimeout(atlasRefreshDomainTabs, 600);
});
