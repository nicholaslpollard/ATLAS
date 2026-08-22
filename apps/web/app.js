"use strict";

const $ = (id) => document.getElementById(id);
let currentStatus = null;
let pendingSwitchTarget = null;
let sessionState = null;

function text(id, value) {
  const node = $(id);
  if (node) node.textContent = value == null ? "—" : String(value);
}

function stateClass(value) {
  const normalized = String(value || "").toUpperCase();
  if (["HEALTHY", "AVAILABLE", "COMPLETED", "AUTHORIZED"].includes(normalized)) return "state-ok";
  if (["DEGRADED", "UNPOLLED", "AWAITING_CONFIRMATION", "REQUESTED", "EXECUTING"].includes(normalized)) return "state-warn";
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

function boolWord(value, yes = "Yes", no = "No") {
  return value === true ? yes : value === false ? no : "—";
}

function displayBrokerName(value) {
  const textValue = String(value || "");
  return textValue ? textValue[0].toUpperCase() + textValue.slice(1) : "—";
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
    : "Provider-write endpoints are disabled. Live execution is not promoted. Broker switching changes only ATLAS local routing after both paper brokers reconcile flat.";
}

function switchControlsAllowed(system, broker) {
  return Boolean(
    system
      && system.phase15
      && system.phase15.accepted
      && system.runtime_state_valid
      && system.action_ledger_valid
      && !system.provider_write_uncertain
      && Number(system.active_action_count || 0) === 0
      && !(system.selected_broker === broker && system.selected_environment === "paper")
  );
}

function brokerCard(row, system) {
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

  const actions = document.createElement("div");
  actions.className = "broker-actions";
  const note = document.createElement("div");
  note.className = "muted";
  const selected = system.selected_broker === row.broker && system.selected_environment === "paper";
  note.textContent = selected
    ? "Current ATLAS paper routing"
    : "Switch requires both paper brokers flat";
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = selected ? "Selected" : `Review switch to ${displayBrokerName(row.broker)}`;
  button.disabled = selected || !switchControlsAllowed(system, row.broker);
  button.addEventListener("click", () => reviewBrokerSwitch(row.broker));
  actions.append(note, button);
  card.appendChild(actions);
  return card;
}

function renderBrokers(rows, system) {
  const root = $("brokers");
  clear(root);
  (rows || []).forEach((row) => root.appendChild(brokerCard(row, system || {})));
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

async function ensureSession() {
  if (sessionState) return sessionState;
  const payload = await getJson("/api/v1/session");
  if (!payload.csrf_token || !payload.header_name) {
    throw new Error("Local control-plane session could not be established");
  }
  sessionState = {
    token: payload.csrf_token,
    headerName: payload.header_name,
  };
  return sessionState;
}

async function postJson(path, payload) {
  const session = await ensureSession();
  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  headers[session.headerName] = session.token;
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers,
    body: JSON.stringify(payload),
  });
  const responsePayload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = responsePayload.detail ? `: ${responsePayload.detail}` : "";
    throw new Error(`${responsePayload.error || `HTTP ${response.status}`}${detail}`);
  }
  return responsePayload;
}

function randomHex(byteCount = 12) {
  const bytes = new Uint8Array(byteCount);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}

function brokerFlatSummary(row) {
  if (!row) return "Missing status";
  if (row.state !== "AVAILABLE") return `${row.state || "UNKNOWN"}${row.error_code ? ` · ${row.error_code}` : ""}`;
  return `${row.open_orders.length} open orders · ${row.positions.length} positions · ${row.safe_to_switch_broker ? "flat" : "blocked"}`;
}

function assertSwitchReviewSafe(status, targetBroker) {
  const system = status.system || {};
  if (!system.phase15 || !system.phase15.accepted) throw new Error("Phase 15 acceptance is required");
  if (!system.runtime_state_valid) throw new Error("Runtime state is invalid; ATLAS remains fail-closed");
  if (!system.action_ledger_valid) throw new Error("Action ledger is invalid; ATLAS remains fail-closed");
  if (system.provider_write_uncertain) throw new Error("Provider-write uncertainty blocks broker switching");
  if (Number(system.active_action_count || 0) !== 0) throw new Error("An existing control-plane action must be resolved first");
  if (system.selected_broker === targetBroker && system.selected_environment === "paper") {
    throw new Error(`${displayBrokerName(targetBroker)} is already selected`);
  }
  const rows = status.brokers || [];
  if (rows.length !== 2) throw new Error("Both paper broker states are required");
  for (const row of rows) {
    if (row.state !== "AVAILABLE" || row.reconciled !== true) {
      throw new Error(`${displayBrokerName(row.broker)} could not be reconciled. No routing change was requested.`);
    }
    if (row.safe_to_switch_broker !== true) {
      const orders = Array.isArray(row.open_orders) ? row.open_orders.length : "unknown";
      const positions = Array.isArray(row.positions) ? row.positions.length : "unknown";
      throw new Error(`${displayBrokerName(row.broker)} is not flat (${orders} open orders, ${positions} positions). ATLAS did not cancel or close anything.`);
    }
  }
}

function openSwitchDialog(status, targetBroker) {
  pendingSwitchTarget = targetBroker;
  const system = status.system || {};
  const rows = Object.fromEntries((status.brokers || []).map((row) => [row.broker, row]));
  text("switch-summary", `Change ATLAS paper routing to ${displayBrokerName(targetBroker)} only after a fresh flat-state check.`);
  text(
    "switch-current",
    system.selected_broker && system.selected_environment
      ? `${displayBrokerName(system.selected_broker)} / ${system.selected_environment}`
      : "Not selected"
  );
  text("switch-target", `${displayBrokerName(targetBroker)} / paper`);
  text("switch-webull", brokerFlatSummary(rows.webull));
  text("switch-alpaca", brokerFlatSummary(rows.alpaca));
  $("switch-dialog").showModal();
}

async function reviewBrokerSwitch(targetBroker) {
  clearError();
  const status = await loadStatus({ refreshBrokers: true });
  assertSwitchReviewSafe(status, targetBroker);
  openSwitchDialog(status, targetBroker);
}

async function executePendingSwitch() {
  const targetBroker = pendingSwitchTarget;
  if (!targetBroker) throw new Error("No broker switch is pending confirmation");
  const actionId = `switch-${randomHex(12)}`;
  const requestResult = await postJson("/api/v1/actions/request", {
    action_id: actionId,
    action_kind: "BROKER_SWITCH",
    requested_at_utc: new Date().toISOString(),
    explicit_user_request: true,
    idempotency_key: `browser-${actionId}`,
    target_broker: targetBroker,
    environment: "paper",
    reason: "explicit manual browser broker selection",
  });
  const fingerprint = requestResult.record && requestResult.record.request_fingerprint;
  if (!fingerprint) throw new Error("Broker-switch request did not return an authority fingerprint");
  await postJson(`/api/v1/actions/${actionId}/confirm`, {
    grant_id: `grant-${randomHex(10)}`,
    action_id: actionId,
    action_fingerprint: fingerprint,
    scope: "BROKER_SWITCH",
    confirmed_at_utc: new Date().toISOString(),
    one_time: true,
  });
  const processed = await postJson(`/api/v1/actions/${actionId}/process`, { process: true });
  pendingSwitchTarget = null;
  $("switch-dialog").close();
  await loadStatus({ refreshBrokers: true });
  if (!processed.record || processed.record.state !== "COMPLETED") {
    const code = processed.record && processed.record.error_code ? processed.record.error_code : "BROKER_SWITCH_BLOCKED";
    throw new Error(`${code}. ATLAS made no provider write and did not cancel or close exposure.`);
  }
}

function showError(error) {
  const box = $("error-box");
  box.hidden = false;
  box.textContent = `Control plane operation failed: ${error instanceof Error ? error.message : String(error)}`;
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
  currentStatus = status;
  renderSystem(status);
  renderBrokers(status.brokers || [], status.system || {});
  renderActions(actions.actions || []);
  return status;
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
  const dialog = $("switch-dialog");
  const cancel = $("switch-cancel");
  const confirm = $("switch-confirm");

  local.addEventListener("click", () => runButton(local, () => loadStatus({ refreshBrokers: false })));
  brokers.addEventListener("click", () => runButton(brokers, () => loadStatus({ refreshBrokers: true })));
  cancel.addEventListener("click", () => {
    pendingSwitchTarget = null;
    dialog.close();
  });
  confirm.addEventListener("click", () => runButton(confirm, async () => {
    try {
      await executePendingSwitch();
    } catch (error) {
      pendingSwitchTarget = null;
      if (dialog.open) dialog.close();
      throw error;
    }
  }));

  loadStatus({ refreshBrokers: false }).catch(showError);
});
