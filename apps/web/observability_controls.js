"use strict";

const phase19Controls = {
  timer: null,
  intervalSeconds: 0,
  refreshInFlight: false,
};

function phase19ControlById(id) {
  return document.getElementById(id);
}

function phase19ControlClear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function phase19BooleanState(value) {
  return value === true ? "ready-check-pass" : "ready-check-fail";
}

function ensurePhase19WorkspaceNavigation() {
  if (phase19ControlById("phase19-workspace-nav")) return;
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;

  const nav = document.createElement("nav");
  nav.id = "phase19-workspace-nav";
  nav.className = "workspace-nav";
  nav.setAttribute("aria-label", "ATLAS workspace sections");

  const label = document.createElement("div");
  label.className = "workspace-nav-label";
  const mark = document.createElement("span");
  mark.className = "workspace-nav-mark";
  mark.textContent = "ATLAS";
  const mode = document.createElement("span");
  mode.className = "workspace-nav-mode";
  mode.textContent = "LOCAL · READ ONLY";
  label.append(mark, mode);

  const links = document.createElement("div");
  links.className = "workspace-nav-links";
  [
    ["Overview", "#safety-banner"],
    ["Pipeline", "#pipeline-stages"],
    ["Paper ops", "#paper-dashboard"],
    ["Candidates", "#candidate-search"],
    ["AI audit", "#ai-date"],
    ["Outcomes", "#outcome-count"],
    ["Brokers", "#brokers"],
    ["Actions", "#actions-table"],
    ["Lineage", "#lineage-merge"],
  ].forEach(([text, href]) => {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = text;
    links.appendChild(link);
  });

  nav.append(label, links);
  topbar.insertAdjacentElement("afterend", nav);
}

function ensurePhase19ReadinessControls() {
  if (phase19ControlById("phase19-readiness-controls")) return;
  const pipeline = phase19ControlById("pipeline-stages");
  if (!pipeline) return;

  const section = document.createElement("section");
  section.id = "phase19-readiness-controls";
  section.className = "card readiness-controls-card";

  const header = document.createElement("div");
  header.className = "readiness-control-header";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Phase 18 operator assist";
  const title = document.createElement("h2");
  title.textContent = "Market-input checklist";
  const description = document.createElement("p");
  description.className = "muted";
  description.textContent = "Diagnostic only. Even when every market input passes, explicit paper-provider mutation authorization is still required.";
  copy.append(eyebrow, title, description);

  const refreshControl = document.createElement("label");
  refreshControl.className = "local-refresh-control";
  const refreshLabel = document.createElement("span");
  refreshLabel.className = "label";
  refreshLabel.textContent = "Local observability auto-refresh";
  const select = document.createElement("select");
  select.id = "local-observability-interval";
  [
    ["Off", "0"],
    ["Every 5 seconds", "5"],
    ["Every 15 seconds", "15"],
    ["Every 30 seconds", "30"],
  ].forEach(([labelText, value]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labelText;
    select.appendChild(option);
  });
  refreshControl.append(refreshLabel, select);
  header.append(copy, refreshControl);

  const list = document.createElement("div");
  list.id = "phase18-input-checklist";
  list.className = "readiness-checklist";

  const footer = document.createElement("div");
  footer.className = "readiness-control-footer";
  const status = document.createElement("span");
  status.id = "local-observability-status";
  status.className = "muted";
  status.textContent = "Auto-refresh off. Manual intelligence refresh remains available.";
  const safety = document.createElement("strong");
  safety.className = "state-warn";
  safety.textContent = "No automatic broker refresh · no mutation authority";
  footer.append(status, safety);

  section.append(header, list, footer);
  pipeline.insertAdjacentElement("afterend", section);

  select.addEventListener("change", () => {
    setPhase19LocalRefreshInterval(Number(select.value));
  });
}

function renderPhase18InputChecklist(payload) {
  ensurePhase19ReadinessControls();
  const root = phase19ControlById("phase18-input-checklist");
  phase19ControlClear(root);
  if (!root) return;

  const live = payload.live_market || {};
  const inputs = live.phase18_market_inputs || {};
  const checks = [
    ["Snapshot within accepted quote-age cap", inputs.snapshot_within_quote_age_cap],
    ["Connection SUBSCRIBED", inputs.subscribed],
    ["Feed REALTIME", inputs.realtime],
    ["Expected delay = 0", inputs.delay_zero],
    ["No open transport gap", inputs.no_open_transport_gap],
    ["Regular U.S. equity session", inputs.regular_session],
    ["Fresh quote within accepted age cap", inputs.has_fresh_quote_within_age_cap],
  ];

  checks.forEach(([labelText, passed]) => {
    const item = document.createElement("div");
    item.className = `readiness-check ${phase19BooleanState(passed)}`;
    const icon = document.createElement("span");
    icon.className = "readiness-check-icon";
    icon.textContent = passed === true ? "✓" : "×";
    const label = document.createElement("span");
    label.textContent = labelText;
    item.append(icon, label);
    root.appendChild(item);
  });

  const state = document.createElement("div");
  state.className = "readiness-check readiness-authority-reminder";
  const icon = document.createElement("span");
  icon.className = "readiness-check-icon";
  icon.textContent = "!";
  const text = document.createElement("span");
  text.textContent = `Market input display: ${inputs.state || "UNAVAILABLE"}. Explicit Phase 18 paper-mutation authorization remains separately required.`;
  state.append(icon, text);
  root.appendChild(state);
}

async function refreshPhase19LocalObservability() {
  if (phase19Controls.refreshInFlight || document.hidden) return;
  phase19Controls.refreshInFlight = true;
  const status = phase19ControlById("local-observability-status");
  try {
    if (status) status.textContent = "Refreshing local observability…";
    const response = await fetch("/api/v1/observability", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    if (typeof window.renderObservability === "function") {
      window.renderObservability(payload);
    }
    renderPhase18InputChecklist(payload);
    window.dispatchEvent(new CustomEvent("atlas:observability-refreshed", {
      detail: { generatedAtUtc: payload.generated_at_utc || null },
    }));
    if (status) {
      const suffix = phase19Controls.intervalSeconds > 0
        ? ` Auto-refresh every ${phase19Controls.intervalSeconds}s.`
        : " Auto-refresh off.";
      status.textContent = `Local observability refreshed.${suffix}`;
    }
  } catch (exc) {
    if (status) {
      status.textContent = `Local observability refresh failed: ${exc instanceof Error ? exc.message : String(exc)}`;
    }
  } finally {
    phase19Controls.refreshInFlight = false;
  }
}

function setPhase19LocalRefreshInterval(seconds) {
  if (phase19Controls.timer !== null) {
    window.clearInterval(phase19Controls.timer);
    phase19Controls.timer = null;
  }
  phase19Controls.intervalSeconds = [5, 15, 30].includes(seconds) ? seconds : 0;
  const status = phase19ControlById("local-observability-status");
  if (phase19Controls.intervalSeconds === 0) {
    if (status) status.textContent = "Auto-refresh off. Manual intelligence refresh remains available.";
    return;
  }
  if (status) {
    status.textContent = `Local observability auto-refresh enabled every ${phase19Controls.intervalSeconds}s. Broker refresh remains manual.`;
  }
  refreshPhase19LocalObservability();
  phase19Controls.timer = window.setInterval(
    refreshPhase19LocalObservability,
    phase19Controls.intervalSeconds * 1000
  );
}

window.addEventListener("visibilitychange", () => {
  const status = phase19ControlById("local-observability-status");
  if (document.hidden) {
    if (status && phase19Controls.intervalSeconds > 0) {
      status.textContent = "Local observability auto-refresh paused while this tab is hidden.";
    }
    return;
  }
  if (phase19Controls.intervalSeconds > 0) {
    refreshPhase19LocalObservability();
  }
});

window.addEventListener("DOMContentLoaded", () => {
  ensurePhase19WorkspaceNavigation();
  ensurePhase19ReadinessControls();
  refreshPhase19LocalObservability();
});
