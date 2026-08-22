"use strict";

const $ = (id) => document.getElementById(id);

function text(id, value) {
  const node = $(id);
  if (node) node.textContent = value == null ? "—" : String(value);
}

function stateClass(value) {
  const normalized = String(value || "").toUpperCase();
  if (["HEALTHY", "AVAILABLE", "COMPLETED", "AUTHORIZED"].includes(normalized)) return "state-ok";
  if (["DEGRADED", "UNPOLLED", "AWAITING_CONFIRMATION", "REQUESTED"].includes(normalized)) return "state-warn";
  if (["BLOCKED", "ERROR", "UNAVAILABLE", "FAILED", "UNCERTAIN"].includes(normalized)) return "state-danger";
  return "state-muted";
}

function setMetric(id, value, className) {
  const node = $(id);
  if (!node) return;
  node.textContent = value;
  node.className = `metric ${className || ""}`.trim();
}

function money(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(number);
}

function shortHash(value) {
  const s = String(value || "");
  if (!s) return "—";
  return s.length > 20 ? `${s.slice(0, 12)}…${s.slice(-8)}` : s;
}

function boolWord(value, yes = "Yes", no = "No") {
  return value === true ? yes : value === false ? no : "—";
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function appendStat(parent, label, value, className = "") {
  const stat = document.createElement("div");
  stat.className = "stat";
  const labelNode = document.createElement("div");
  labelNode.className = "label";
  labelNode.textContent = label;
  const valueNode = document.createElement("div");
  valueNode.className = `value ${className}`.trim();
  valueNode.textContent = value;
  stat.append(labelNode, valueNode);
  parent.appendChild(stat);
}

function renderSystem(payload) {
  const system = payload.system || {};
  const phase15 = system.phase15 || {};
  const health = system.health || "UNKNOWN";
  setMetric("system-health", health, stateClass(health));
  text(
    "health-detail",
    `Runtime ${system.runtime_state_valid ? "valid" : "invalid"} · ledger ${system.action_ledger_valid ? "valid" : "invalid"}`
  );

  const routing = system.selected_broker && system.selected_environment
    ? `${system.selected_broker} / ${system.selected_environment}`
    : "Not selected";
  setMetric("selected-routing", routing, routing === "Not selected" ? "state-warn" : "state-ok");
  text(
    "runtime-detail",
    `source ${system.runtime_state_source || "—"} · revision ${system.runtime_revision ?? 0}`
  );

  setMetric(
    "phase15-state",
    phase15.accepted ? "Accepted" : "Blocked",
    phase15.accepted ? "state-ok" : "state-danger"
  );
  text(
    "phase15-detail",
    `${phase15.as_of_date || "no acceptance date"} · execution cases ${phase15.execution_case_count ?? "—"}`
  );

  setMetric(
    "ledger-state",
    system.action_ledger_valid ? "Verified" : "Invalid",
    system.action_ledger_valid ? "state-ok" : "state-danger"
  );
  text(
    "ledger-detail",
    `${system.action_count ?? 0} actions · ${system.active_action_count ?? 0} active · ${system.uncertain_action_count ?? 0} uncertain`
  );

  text("lineage-merge", system.accepted_phase15_merge_sha || "—");
  text("lineage-phase15", system.accepted_phase15_policy_fingerprint || phase15.policy_fingerprint || "—");
  text("lineage-phase16", system.phase16_policy_fingerprint || "—");
  text("lineage-foundation", phase15.cumulative_foundation_fingerprint || "—");

  const banner = $("safety-banner");
  banner.className = system.provider_write_uncertain ? "banner danger" : "banner warning";
  banner.textContent = system.provider_write_uncertain
    ? "ATLAS is fail-closed because provider-write uncertainty or invalid operational state exists. Provider-write endpoints remain disabled."
    : "Provider-write endpoints are disabled. Live execution is not promoted. Browser actions cannot bypass Phase 15 gates.";
}

function brokerCard(row) {
  const card = document.createElement("article");
  card.className = "card";

  const head = document.createElement("div");
  head.className = "broker-title";
  const titleWrap = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Paper provider";
  const title = document.createElement("h3");
  title.textContent = row.broker || "unknown";
  titleWrap.append(eyebrow, title);
  const pill = document.createElement("span");
  pill.className = `pill ${stateClass(row.state)}`.trim();
  pill.textContent = row.state || "UNKNOWN";
  head.append(titleWrap, pill);
  card.appendChild(head);

  const credentialLine = document.createElement("div");
  credentialLine.className = "muted";
  credentialLine.textContent = `Credentials configured: ${boolWord(row.credentials && row.credentials.ready)}`;
  card.appendChild(credentialLine);

  const stats = document.createElement("div");
  stats.className = "broker-stats";
  appendStat(stats, "Account", row.account ? row.account.account_ref : "Not polled");
  appendStat(stats, "Equity", row.account ? money(row.account.equity) : "—");
  appendStat(stats, "Open orders", row.open_orders ? String(row.open_orders.length) : "—");
  appendStat(stats, "Positions", row.positions ? String(row.positions.length) : "—");
  appendStat(stats, "Reconciled", boolWord(row.reconciled));
  appendStat(
    stats,
    "Safe to switch",
    boolWord(row.safe_to_switch_broker),
    row.safe_to_switch_broker === true ? "state-ok" : row.safe_to_switch_broker === false ? "state-warn" : ""
  );
  card.appendChild(stats);

  if (row.error_code) {
    const error = document.createElement("div");
    error.className = "muted state-danger";
    error.textContent = `Status: ${row.error_code}`;
    card.appendChild(error);
  }
  return card;
}

function renderBrokers(rows) {
  const root = $("brokers");
  clear(root);
  (rows || []).forEach((row) => root.appendChild(brokerCard(row)));
}

function renderActions(records) {
  const empty = $("actions-empty");
  const table = $("actions-table");
  const body = $("actions-body");
  clear(body);
  if (!records || records.length === 0) {
    empty.hidden = false;
    table.hidden = true;
    return;
  }
  empty.hidden = true;
  table.hidden = false;
  records
    .slice()
    .sort((a, b) => String(b.updated_at_utc || "").localeCompare(String(a.updated_at_utc || "")))
    .forEach((record) => {
      const request = record.request || {};
      const row = document.createElement("tr");
      const values = [
        request.action_kind || "—",
        request.target_broker ? `${request.target_broker} / ${request.environment || "—"}` : request.environment || "—",
        record.state || "—",
        String(record.revision ?? "—"),
        record.provider_write_attempted ? "Attempted" : "No",
      ];
      values.forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        if (index === 2) cell.className = stateClass(value);
        if (index === 4 && value === "No") cell.className = "state-ok";
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
}

async function getJson(path) {
  const response = await fetch(path, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function showError(error) {
  const box = $("error-box");
  box.hidden = false;
  box.textContent = `Control plane status read failed: ${error instanceof Error ? error.message : String(error)}`;
}

function clearError() {
  const box = $("error-box");
  box.hidden = true;
  box.textContent = "";
}

async function loadStatus({ refreshBrokers = false } = {}) {
  clearError();
  const suffix = refreshBrokers ? "?refresh=1" : "";
  const [status, actions] = await Promise.all([
    getJson(`/api/v1/status/full${suffix}`),
    getJson("/api/v1/actions"),
  ]);
  renderSystem(status);
  renderBrokers(status.brokers || []);
  renderActions(actions.actions || []);
}

async function runButton(button, work) {
  button.disabled = true;
  try {
    await work();
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const local = $("refresh-local");
  const brokers = $("refresh-brokers");
  local.addEventListener("click", () => runButton(local, () => loadStatus({ refreshBrokers: false })));
  brokers.addEventListener("click", () => runButton(brokers, () => loadStatus({ refreshBrokers: true })));
  loadStatus({ refreshBrokers: false }).catch(showError);
});
