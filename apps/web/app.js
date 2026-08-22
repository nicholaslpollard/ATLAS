"use strict";

const $ = (id) => document.getElementById(id);
let currentStatus = null;
let pendingSwitchTarget = null;
let pendingCleanupReview = null;
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
    : "Provider-write endpoints are disabled. Live execution is not promoted. Broker switching changes only local routing; cleanup review can inspect exact broker resources but cannot cancel or flatten them.";
}

function baseControlsAllowed(system) {
  return Boolean(
    system
      && system.phase15
      && system.phase15.accepted
      && system.runtime_state_valid
      && system.action_ledger_valid
      && !system.provider_write_uncertain
      && Number(system.active_action_count || 0) === 0
  );
}

function switchControlsAllowed(system, broker) {
  return Boolean(
    baseControlsAllowed(system)
      && !(system.selected_broker === broker && system.selected_environment === "paper")
  );
}

function cleanupControlsAllowed(system, row, kind) {
  if (!baseControlsAllowed(system) || !row || row.state !== "AVAILABLE" || row.reconciled !== true) {
    return false;
  }
  const orders = Array.isArray(row.open_orders) ? row.open_orders : [];
  const positions = Array.isArray(row.positions) ? row.positions : [];
  if (kind === "CANCEL_OPEN_ORDERS") return orders.length > 0;
  if (kind === "FLATTEN_POSITIONS") return orders.length === 0 && positions.length > 0;
  return false;
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

  const orderCount = Array.isArray(row.open_orders) ? row.open_orders.length : 0;
  const positionCount = Array.isArray(row.positions) ? row.positions.length : 0;
  const cleanup = document.createElement("div");
  cleanup.className = "broker-actions cleanup-actions";
  const cleanupNote = document.createElement("div");
  cleanupNote.className = "muted";
  cleanupNote.textContent = orderCount > 0
    ? "Review-only cleanup: open orders must be resolved before position flatten review."
    : "Review-only cleanup: exact resources are re-reconciled; provider writes remain disabled.";
  const cleanupButtons = document.createElement("div");
  cleanupButtons.className = "cleanup-button-row";

  const cancelButton = document.createElement("button");
  cancelButton.type = "button";
  cancelButton.textContent = orderCount > 0
    ? `Review ${orderCount} open order${orderCount === 1 ? "" : "s"}`
    : "No open orders";
  cancelButton.disabled = !cleanupControlsAllowed(system, row, "CANCEL_OPEN_ORDERS");
  cancelButton.addEventListener("click", () => reviewBrokerCleanup(row.broker, "CANCEL_OPEN_ORDERS"));

  const flattenButton = document.createElement("button");
  flattenButton.type = "button";
  flattenButton.textContent = positionCount > 0
    ? `Review ${positionCount} position${positionCount === 1 ? "" : "s"}`
    : "No positions";
  flattenButton.disabled = !cleanupControlsAllowed(system, row, "FLATTEN_POSITIONS");
  flattenButton.addEventListener("click", () => reviewBrokerCleanup(row.broker, "FLATTEN_POSITIONS"));

  cleanupButtons.append(cancelButton, flattenButton);
  cleanup.append(cleanupNote, cleanupButtons);
  card.appendChild(cleanup);
  return card;
}

function renderBrokers(rows, system) {
  const root = $("brokers");
  clear(root);
  (rows || []).forEach((row) => root.appendChild(brokerCard(row, system || {})));
}

function actionCanBeAbandoned(record) {
  return Boolean(
    record
      && !record.provider_write_attempted
      && !record.provider_write_uncertain
      && ["AWAITING_CONFIRMATION", "AUTHORIZED"].includes(String(record.state || ""))
  );
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

      const recovery = document.createElement("td");
      recovery.className = "recovery-cell";
      if (actionCanBeAbandoned(record)) {
        const abandon = document.createElement("button");
        abandon.type = "button";
        abandon.className = "danger-action";
        abandon.textContent = "Abandon pre-write";
        abandon.addEventListener("click", () => runButton(abandon, () => abandonAction(request.action_id)));
        recovery.appendChild(abandon);
      } else {
        recovery.textContent = "—";
      }
      row.appendChild(recovery);
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

function cleanupKindLabel(kind) {
  if (kind === "CANCEL_OPEN_ORDERS") return "Open-order cancellation review";
  if (kind === "FLATTEN_POSITIONS") return "Position flatten review";
  return String(kind || "Unknown cleanup review");
}

function findBrokerRow(status, broker) {
  return (status.brokers || []).find((row) => row.broker === broker) || null;
}

function cleanupInventorySummary(row) {
  if (!row) return "Broker state unavailable";
  const orders = Array.isArray(row.open_orders) ? row.open_orders.length : 0;
  const positions = Array.isArray(row.positions) ? row.positions.length : 0;
  return `${orders} open order${orders === 1 ? "" : "s"} · ${positions} position${positions === 1 ? "" : "s"}`;
}

function assertCleanupReviewSafe(status, broker, kind) {
  const system = status.system || {};
  if (!baseControlsAllowed(system)) {
    throw new Error("Cleanup review requires accepted Phase 15, valid runtime/audit state, zero uncertainty, and no other active action");
  }
  const row = findBrokerRow(status, broker);
  if (!row || row.state !== "AVAILABLE" || row.reconciled !== true) {
    throw new Error(`${displayBrokerName(broker)} must complete a fresh read-only reconciliation before cleanup review`);
  }
  const orders = Array.isArray(row.open_orders) ? row.open_orders : [];
  const positions = Array.isArray(row.positions) ? row.positions : [];
  if (kind === "CANCEL_OPEN_ORDERS" && orders.length === 0) {
    throw new Error("There are no open orders to review for cancellation");
  }
  if (kind === "FLATTEN_POSITIONS") {
    if (orders.length > 0) throw new Error("Open orders must be reviewed separately before position flatten review");
    if (positions.length === 0) throw new Error("There are no positions to review for flattening");
  }
  return row;
}

function renderCleanupTargets(plan) {
  const root = $("cleanup-targets");
  clear(root);
  const cancelTargets = Array.isArray(plan && plan.cancel_targets) ? plan.cancel_targets : [];
  const flattenTargets = Array.isArray(plan && plan.flatten_targets) ? plan.flatten_targets : [];
  const targets = cancelTargets.length ? cancelTargets : flattenTargets;
  if (targets.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty compact";
    empty.textContent = "Fresh reconciliation found no resources in this review plan.";
    root.appendChild(empty);
    return;
  }
  targets.forEach((target) => {
    const item = document.createElement("div");
    item.className = "cleanup-target";
    const title = document.createElement("div");
    title.className = "cleanup-target-title";
    const detail = document.createElement("div");
    detail.className = "cleanup-target-detail";
    if (cancelTargets.length) {
      title.textContent = `${target.ticker} · ${target.client_order_id}`;
      detail.textContent = `${target.side} · ${target.status} · requested ${target.requested_quantity} · filled ${target.filled_quantity}`;
    } else {
      title.textContent = target.ticker;
      detail.textContent = `quantity ${target.quantity} · close side ${target.required_close_side} · market value ${money(target.market_value)}`;
    }
    item.append(title, detail);
    root.appendChild(item);
  });
}

function openCleanupDialog(status, broker, kind) {
  const row = findBrokerRow(status, broker);
  pendingCleanupReview = {
    broker,
    kind,
    stage: "initial",
    actionId: null,
    actionFingerprint: null,
    actionGrant: null,
    planFingerprint: null,
    planGrant: null,
    plan: null,
  };
  text(
    "cleanup-title",
    kind === "CANCEL_OPEN_ORDERS" ? "Review open-order cleanup" : "Review position flattening"
  );
  text(
    "cleanup-summary",
    `Authorize ATLAS to create an audited review request for ${displayBrokerName(broker)}. After authorization it will re-read the paper account and capture the exact resource set. No provider mutation endpoint is available.`
  );
  text("cleanup-broker", `${displayBrokerName(broker)} / paper`);
  text("cleanup-kind", cleanupKindLabel(kind));
  text("cleanup-inventory", cleanupInventorySummary(row));
  text("cleanup-fingerprint", "Not generated");
  text("cleanup-expiry", "—");
  const targets = $("cleanup-targets");
  clear(targets);
  const empty = document.createElement("div");
  empty.className = "empty compact";
  empty.textContent = "Authorize plan generation to capture the exact resource set.";
  targets.appendChild(empty);
  const result = $("cleanup-result");
  result.hidden = true;
  result.textContent = "";
  result.className = "banner ok cleanup-result";
  const cancel = $("cleanup-cancel");
  cancel.hidden = false;
  cancel.textContent = "Cancel review";
  const confirm = $("cleanup-confirm");
  confirm.textContent = "Authorize plan generation";
  $("cleanup-dialog").showModal();
}

async function reviewBrokerCleanup(broker, kind) {
  clearError();
  const status = await loadStatus({ refreshBrokers: true });
  assertCleanupReviewSafe(status, broker, kind);
  openCleanupDialog(status, broker, kind);
}

async function createAuthorizedCleanupPlan() {
  const pending = pendingCleanupReview;
  if (!pending) throw new Error("No cleanup review is pending");
  if (!pending.actionId) pending.actionId = `cleanup-${randomHex(12)}`;
  const actionId = pending.actionId;
  const requested = await postJson("/api/v1/actions/request", {
    action_id: actionId,
    action_kind: pending.kind,
    requested_at_utc: new Date().toISOString(),
    explicit_user_request: true,
    idempotency_key: `browser-${actionId}`,
    target_broker: pending.broker,
    environment: "paper",
    reason: "explicit browser cleanup review only; provider writes disabled",
  });
  const fingerprint = requested.record && requested.record.request_fingerprint;
  if (!fingerprint) throw new Error("Cleanup review request did not return an authority fingerprint");
  pending.actionFingerprint = fingerprint;
  if (!pending.actionGrant) {
    pending.actionGrant = {
      grant_id: `grant-${randomHex(10)}`,
      action_id: actionId,
      action_fingerprint: fingerprint,
      scope: pending.kind,
      confirmed_at_utc: new Date().toISOString(),
      one_time: true,
    };
  }
  await postJson(`/api/v1/actions/${actionId}/confirm`, pending.actionGrant);
  const planned = await postJson(`/api/v1/actions/${actionId}/cleanup-plan`, { plan: true });
  if (!planned.cleanup_plan || !planned.cleanup_plan_fingerprint) {
    throw new Error("Cleanup planner did not return an exact review plan");
  }
  if (planned.provider_write_authorized !== false || planned.provider_write_endpoints_present !== false) {
    throw new Error("Cleanup review authority boundary is invalid; ATLAS remains fail-closed");
  }
  pending.plan = planned.cleanup_plan;
  pending.planFingerprint = planned.cleanup_plan_fingerprint;
  pending.stage = "plan";
  text("cleanup-fingerprint", pending.planFingerprint);
  text("cleanup-expiry", pending.plan.expires_at_utc || "—");
  renderCleanupTargets(pending.plan);
  $("cleanup-cancel").textContent = "Abandon review";
  $("cleanup-confirm").textContent = "Confirm exact resources — no broker changes";
}

function renderCleanupResult(record) {
  const result = $("cleanup-result");
  result.hidden = false;
  const state = String(record && record.state || "UNKNOWN");
  const code = String(record && record.error_code || "");
  if (state === "COMPLETED") {
    result.className = "banner ok cleanup-result";
    result.textContent = "Review closed. Fresh reconciliation found no cleanup currently required. No provider write was attempted.";
  } else if (state === "BLOCKED" && ["CANCEL_PROVIDER_WRITES_DISABLED", "FLATTEN_PROVIDER_WRITES_DISABLED"].includes(code)) {
    result.className = "banner warning cleanup-result";
    result.textContent = "Exact resources were confirmed and re-reconciled. ATLAS made no broker changes because cleanup provider writes are disabled. The review is now terminal.";
  } else {
    result.className = "banner danger cleanup-result";
    result.textContent = `Review closed fail-closed: ${code || state}. No provider write was attempted.`;
  }
}

async function confirmCleanupPlanAndCloseReview() {
  const pending = pendingCleanupReview;
  if (!pending || !pending.actionId || !pending.actionFingerprint || !pending.planFingerprint) {
    throw new Error("Cleanup review is missing exact plan authority");
  }
  if (!pending.planGrant) {
    pending.planGrant = {
      grant_id: `plan-grant-${randomHex(10)}`,
      action_id: pending.actionId,
      action_fingerprint: pending.actionFingerprint,
      cleanup_plan_fingerprint: pending.planFingerprint,
      confirmed_at_utc: new Date().toISOString(),
      one_time: true,
    };
  }
  await postJson(
    `/api/v1/actions/${pending.actionId}/cleanup-plan/confirm`,
    pending.planGrant
  );
  pending.stage = "confirmed";
  return closeConfirmedCleanupReview();
}

async function closeConfirmedCleanupReview() {
  const pending = pendingCleanupReview;
  if (!pending || !pending.actionId) throw new Error("Cleanup review action is unavailable");
  const closed = await postJson(
    `/api/v1/actions/${pending.actionId}/cleanup-plan/close-review`,
    { close_review: true }
  );
  if (closed.provider_write_attempted !== false || closed.provider_write_endpoint_invoked !== false) {
    throw new Error("Cleanup review attempted a provider write; ATLAS remains fail-closed");
  }
  pending.stage = "closed";
  renderCleanupResult(closed.record || {});
  $("cleanup-cancel").hidden = true;
  $("cleanup-confirm").textContent = "Close";
  await loadStatus({ refreshBrokers: true });
}

async function advanceCleanupReview() {
  const pending = pendingCleanupReview;
  if (!pending) throw new Error("No cleanup review is pending");
  if (pending.stage === "initial") {
    try {
      await createAuthorizedCleanupPlan();
    } catch (error) {
      await bestEffortAbandonCleanupReview();
      const dialog = $("cleanup-dialog");
      if (dialog.open) dialog.close();
      pendingCleanupReview = null;
      throw error;
    }
    return;
  }
  if (pending.stage === "plan") {
    await confirmCleanupPlanAndCloseReview();
    return;
  }
  if (pending.stage === "confirmed") {
    await closeConfirmedCleanupReview();
    return;
  }
  if (pending.stage === "closed") {
    $("cleanup-dialog").close();
    pendingCleanupReview = null;
    return;
  }
  throw new Error("Unknown cleanup review stage");
}

async function bestEffortAbandonCleanupReview() {
  const pending = pendingCleanupReview;
  if (!pending || !pending.actionId || pending.stage === "closed") return;
  try {
    await postJson(`/api/v1/actions/${pending.actionId}/abandon`, { abandon: true });
  } catch (error) {
    try {
      const record = await getJson(`/api/v1/actions/${pending.actionId}`);
      if (!["BLOCKED", "COMPLETED", "FAILED"].includes(String(record.state || ""))) throw error;
    } catch {
      throw error;
    }
  }
}

async function abandonCleanupReview() {
  const pending = pendingCleanupReview;
  if (pending && pending.stage !== "closed") {
    await bestEffortAbandonCleanupReview();
    await loadStatus({ refreshBrokers: false });
  }
  const dialog = $("cleanup-dialog");
  if (dialog.open) dialog.close();
  pendingCleanupReview = null;
}

async function abandonAction(actionId) {
  if (!actionId) throw new Error("Action id is required for abandon");
  const result = await postJson(`/api/v1/actions/${actionId}/abandon`, { abandon: true });
  if (!result.abandoned || result.provider_write_attempted !== false) {
    throw new Error("Pre-write abandon did not complete safely");
  }
  await loadStatus({ refreshBrokers: false });
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
  const switchDialog = $("switch-dialog");
  const switchCancel = $("switch-cancel");
  const switchConfirm = $("switch-confirm");
  const cleanupDialog = $("cleanup-dialog");
  const cleanupCancel = $("cleanup-cancel");
  const cleanupConfirm = $("cleanup-confirm");

  local.addEventListener("click", () => runButton(local, () => loadStatus({ refreshBrokers: false })));
  brokers.addEventListener("click", () => runButton(brokers, () => loadStatus({ refreshBrokers: true })));
  switchCancel.addEventListener("click", () => {
    pendingSwitchTarget = null;
    switchDialog.close();
  });
  switchConfirm.addEventListener("click", () => runButton(switchConfirm, async () => {
    try {
      await executePendingSwitch();
    } catch (error) {
      pendingSwitchTarget = null;
      if (switchDialog.open) switchDialog.close();
      throw error;
    }
  }));

  cleanupCancel.addEventListener("click", () => runButton(cleanupCancel, () => abandonCleanupReview()));
  cleanupDialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    runButton(cleanupCancel, () => abandonCleanupReview());
  });
  cleanupConfirm.addEventListener("click", () => {
    cleanupCancel.disabled = true;
    runButton(cleanupConfirm, async () => {
      try {
        await advanceCleanupReview();
      } finally {
        cleanupCancel.disabled = false;
      }
    });
  });

  loadStatus({ refreshBrokers: false }).catch(showError);
});
