"use strict";

const paperDashboardState = {
  refreshInFlight: false,
};

function paperById(id) {
  return document.getElementById(id);
}

function paperClear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function paperText(value, fallback = "—") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function paperMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Unavailable";
  return Number(value).toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function paperPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "Unavailable";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function paperNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
}

function paperTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function paperStatusClass(status) {
  const value = String(status || "").toUpperCase();
  if (value === "AVAILABLE" || value === "FILLED" || value === "SHADOW_FILLED") return "state-ok";
  if (value === "INVALID" || value === "FAILED" || value === "REJECTED") return "state-danger";
  return "state-warn";
}

function paperCell(text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = paperText(text);
  if (className) cell.className = className;
  return cell;
}

function paperReason(value) {
  if (!Array.isArray(value) || value.length === 0) return "—";
  return value.join(" · ");
}

function paperCard(labelText, metricId, detailId) {
  const article = document.createElement("article");
  article.className = "card";
  const label = document.createElement("div");
  label.className = "label";
  label.textContent = labelText;
  const metric = document.createElement("div");
  metric.id = metricId;
  metric.className = "metric compact-metric";
  metric.textContent = "Loading…";
  article.append(label, metric);
  if (detailId) {
    const detail = document.createElement("div");
    detail.id = detailId;
    detail.className = "muted";
    article.appendChild(detail);
  }
  return article;
}

function paperTableCard(eyebrowText, titleText, emptyId, tableId, bodyId, headers) {
  const article = document.createElement("article");
  article.className = "card table-card";

  const title = document.createElement("div");
  title.className = "reference-lab-title";
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = eyebrowText;
  const heading = document.createElement("h3");
  heading.textContent = titleText;
  title.append(eyebrow, heading);

  const empty = document.createElement("div");
  empty.id = emptyId;
  empty.className = "empty";
  empty.textContent = "No records available.";

  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.id = tableId;
  table.className = "intelligence-table";
  table.hidden = true;
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  const body = document.createElement("tbody");
  body.id = bodyId;
  table.append(thead, body);
  wrap.appendChild(table);
  article.append(title, empty, wrap);
  return article;
}

function ensurePaperDashboard() {
  if (paperById("paper-dashboard")) return;
  const anchor = paperById("phase19-readiness-controls") || paperById("pipeline-stages");
  if (!anchor) return;

  const root = document.createElement("section");
  root.id = "paper-dashboard";

  const head = document.createElement("section");
  head.className = "section-head";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "A34.5 · Operational PAPER observability";
  const title = document.createElement("h2");
  title.textContent = "Paper execution dashboard";
  copy.append(eyebrow, title);
  const description = document.createElement("p");
  description.textContent = "Hash-verified local execution evidence. Market-data health is independent from execution routing and remains visible in the market-input checklist above. Browser polling never refreshes a broker or provider.";
  head.append(copy, description);

  const banner = document.createElement("section");
  banner.id = "paper-dashboard-banner";
  banner.className = "banner warning";
  banner.setAttribute("aria-live", "polite");
  banner.textContent = "Loading local PAPER execution evidence…";

  const summary = document.createElement("section");
  summary.className = "grid summary-grid";
  summary.setAttribute("aria-label", "Paper execution summary");
  summary.append(
    paperCard("Dashboard state", "paper-state", "paper-state-detail"),
    paperCard("Market data", "paper-market-data", "paper-market-data-detail"),
    paperCard("Execution routing", "paper-routing", "paper-routing-detail"),
    paperCard("Last reconciled account", "paper-account", "paper-account-detail"),
    paperCard("Realized gross P&L", "paper-realized", "paper-realized-detail"),
    paperCard("Mutation authority", "paper-writes", "paper-writes-detail")
  );

  const positions = paperTableCard(
    "Authoritative entry evidence",
    "Open ATLAS positions",
    "paper-positions-empty",
    "paper-positions-table",
    "paper-positions-body",
    ["Ticker", "Side", "Qty", "Entry", "Current mark", "Unrealized", "Stop", "Target", "Strategy", "State"]
  );

  const activityGrid = document.createElement("section");
  activityGrid.className = "grid reference-lab-grid";
  activityGrid.append(
    paperTableCard(
      "Deterministic decisions",
      "Recent decision feed",
      "paper-decisions-empty",
      "paper-decisions-table",
      "paper-decisions-body",
      ["Date", "Ticker", "Broker", "Environment", "Disposition", "Reason", "Uncertain"]
    ),
    paperTableCard(
      "Broker lifecycle evidence",
      "Recent order state",
      "paper-orders-empty",
      "paper-orders-table",
      "paper-orders-body",
      ["Updated", "Ticker", "Broker", "Side", "Status", "Requested", "Filled", "Avg fill", "Submission"]
    )
  );

  const history = paperTableCard(
    "Descriptive outcomes only",
    "Completed trades",
    "paper-closed-empty",
    "paper-closed-table",
    "paper-closed-body",
    ["Closed", "Ticker", "Direction", "Broker", "Exit", "Gross P&L", "Gross return", "R", "Net P&L"]
  );

  const health = document.createElement("section");
  health.className = "card readiness-controls-card";
  const healthHead = document.createElement("div");
  healthHead.className = "readiness-control-header";
  const healthCopy = document.createElement("div");
  const healthEyebrow = document.createElement("div");
  healthEyebrow.className = "eyebrow";
  healthEyebrow.textContent = "Safety and provenance";
  const healthTitle = document.createElement("h3");
  healthTitle.textContent = "Runtime evidence health";
  const healthDescription = document.createElement("p");
  healthDescription.className = "muted";
  healthDescription.textContent = "Pre-submit broker reconciliation is labeled separately from post-entry position evidence. Strategy provenance and net P&L remain unavailable until their upstream contracts carry them explicitly.";
  healthCopy.append(healthEyebrow, healthTitle, healthDescription);
  const healthMetric = document.createElement("div");
  healthMetric.id = "paper-health-state";
  healthMetric.className = "metric compact-metric";
  healthMetric.textContent = "Loading…";
  healthHead.append(healthCopy, healthMetric);
  const healthList = document.createElement("div");
  healthList.id = "paper-health-list";
  healthList.className = "readiness-checklist";
  health.append(healthHead, healthList);

  root.append(head, banner, summary, positions, activityGrid, history, health);
  anchor.insertAdjacentElement("afterend", root);
}

function renderPaperRows(payload) {
  const positions = Array.isArray(payload.open_positions) ? payload.open_positions : [];
  const positionBody = paperById("paper-positions-body");
  paperClear(positionBody);
  positions.forEach((item) => {
    const row = document.createElement("tr");
    const pnl = item.unrealized_pnl === null || item.unrealized_pnl === undefined
      ? "Unavailable"
      : `${paperMoney(item.unrealized_pnl)} · ${paperPercent(item.unrealized_return)}`;
    row.append(
      paperCell(item.ticker),
      paperCell(item.side),
      paperCell(paperNumber(item.quantity, 4)),
      paperCell(paperMoney(item.entry_price)),
      paperCell(item.current_mark === null || item.current_mark === undefined ? item.mark_state : paperMoney(item.current_mark)),
      paperCell(pnl),
      paperCell(paperMoney(item.stop)),
      paperCell(paperMoney(item.target)),
      paperCell(item.strategy_id || "Unavailable upstream"),
      paperCell(item.reconciliation_state)
    );
    positionBody.appendChild(row);
  });
  const positionsTable = paperById("paper-positions-table");
  const positionsEmpty = paperById("paper-positions-empty");
  if (positionsTable) positionsTable.hidden = positions.length === 0;
  if (positionsEmpty) {
    positionsEmpty.hidden = positions.length > 0;
    positionsEmpty.textContent = payload.status === "NOT_RUN"
      ? "No Phase15 execution manifest exists yet."
      : "No filled, unclosed ATLAS position evidence is present.";
  }

  const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
  const decisionBody = paperById("paper-decisions-body");
  paperClear(decisionBody);
  decisions.forEach((item) => {
    const row = document.createElement("tr");
    row.append(
      paperCell(item.as_of_date),
      paperCell(item.ticker),
      paperCell(item.broker),
      paperCell(item.environment),
      paperCell(item.disposition),
      paperCell(paperReason(item.reason_codes)),
      paperCell(item.provider_submission_uncertain ? "YES · RECONCILE" : "No", item.provider_submission_uncertain ? "state-danger" : "")
    );
    decisionBody.appendChild(row);
  });
  const decisionsTable = paperById("paper-decisions-table");
  const decisionsEmpty = paperById("paper-decisions-empty");
  if (decisionsTable) decisionsTable.hidden = decisions.length === 0;
  if (decisionsEmpty) decisionsEmpty.hidden = decisions.length > 0;

  const orders = Array.isArray(payload.orders) ? payload.orders : [];
  const orderBody = paperById("paper-orders-body");
  paperClear(orderBody);
  orders.forEach((item) => {
    const row = document.createElement("tr");
    row.append(
      paperCell(paperTime(item.updated_at_utc)),
      paperCell(item.ticker),
      paperCell(item.broker),
      paperCell(item.side),
      paperCell(item.status, paperStatusClass(item.status)),
      paperCell(paperNumber(item.requested_quantity, 4)),
      paperCell(paperNumber(item.filled_quantity, 4)),
      paperCell(item.average_fill_price === null || item.average_fill_price === undefined ? "—" : paperMoney(item.average_fill_price)),
      paperCell(item.existing_order_reused ? "Existing reconciled" : (item.provider_submission_performed ? "Provider submit" : "No submit"))
    );
    orderBody.appendChild(row);
  });
  const ordersTable = paperById("paper-orders-table");
  const ordersEmpty = paperById("paper-orders-empty");
  if (ordersTable) ordersTable.hidden = orders.length === 0;
  if (ordersEmpty) ordersEmpty.hidden = orders.length > 0;

  const closed = Array.isArray(payload.closed_trades) ? payload.closed_trades : [];
  const closedBody = paperById("paper-closed-body");
  paperClear(closedBody);
  closed.forEach((item) => {
    const row = document.createElement("tr");
    row.append(
      paperCell(paperTime(item.closed_at_utc)),
      paperCell(item.ticker),
      paperCell(item.direction),
      paperCell(item.broker),
      paperCell(item.exit_reason),
      paperCell(paperMoney(item.gross_pnl)),
      paperCell(paperPercent(item.gross_return)),
      paperCell(paperNumber(item.realized_r, 2)),
      paperCell("Unavailable · gross-only schema", "state-warn")
    );
    closedBody.appendChild(row);
  });
  const closedTable = paperById("paper-closed-table");
  const closedEmpty = paperById("paper-closed-empty");
  if (closedTable) closedTable.hidden = closed.length === 0;
  if (closedEmpty) closedEmpty.hidden = closed.length > 0;
}

function renderPaperHealth(payload) {
  const health = payload.health || {};
  const healthState = paperById("paper-health-state");
  if (healthState) {
    healthState.textContent = payload.status || "UNAVAILABLE";
    healthState.className = `metric compact-metric ${paperStatusClass(payload.status)}`;
  }
  const root = paperById("paper-health-list");
  paperClear(root);
  if (!root) return;

  const checks = [
    ["Local execution evidence valid", health.local_evidence_valid === true, health.local_evidence_valid === true ? "Verified" : (health.reason || "Unavailable")],
    ["Provider submission uncertainty", health.provider_submission_uncertain !== true, health.provider_submission_uncertain ? "UNCERTAIN · reconciliation required" : "None recorded"],
    ["Reconciliation requirement", health.requires_reconciliation !== true, health.requires_reconciliation ? "REQUIRED" : "No unresolved requirement"],
    ["Automatic broker refresh", health.automatic_broker_refresh === false, health.automatic_broker_refresh === false ? "Disabled" : "Not proven disabled"],
    ["Browser mutation authority", health.browser_mutation_authority === false, health.browser_mutation_authority === false ? "Disabled" : "Not proven disabled"],
    ["LIVE execution promoted", health.live_execution_promoted === false, health.live_execution_promoted === false ? "False" : "Not proven false"],
  ];

  checks.forEach(([labelText, passed, detailText]) => {
    const item = document.createElement("div");
    item.className = `readiness-check ${passed ? "ready-check-pass" : "ready-check-fail"}`;
    const icon = document.createElement("span");
    icon.className = "readiness-check-icon";
    icon.textContent = passed ? "✓" : "×";
    const label = document.createElement("span");
    label.textContent = `${labelText}: ${detailText}`;
    item.append(icon, label);
    root.appendChild(item);
  });

  const mark = document.createElement("div");
  mark.className = "readiness-check readiness-authority-reminder";
  const markIcon = document.createElement("span");
  markIcon.className = "readiness-check-icon";
  markIcon.textContent = "i";
  const markText = document.createElement("span");
  markText.textContent = `Fresh persisted market marks available: ${paperText(health.fresh_mark_count, "0")}. Market-data provider/feed selection is independent of execution broker selection.`;
  mark.append(markIcon, markText);
  root.appendChild(mark);
}

function renderPaperDashboard(payload) {
  ensurePaperDashboard();
  const status = String(payload.status || "UNAVAILABLE").toUpperCase();
  const banner = paperById("paper-dashboard-banner");
  if (banner) {
    banner.className = `banner ${status === "INVALID" ? "danger" : (status === "AVAILABLE" ? "success" : "warning")}`;
    if (status === "NOT_RUN") {
      banner.textContent = "Operational PAPER has not run. The dashboard is connected and waiting for authoritative Phase15 execution evidence.";
    } else if (status === "INVALID") {
      banner.textContent = "Local execution evidence failed path/hash/schema validation. PAPER state is not trusted.";
    } else if (status === "DEGRADED") {
      banner.textContent = "Execution evidence is readable but provider uncertainty or reconciliation is unresolved. Treat execution state as degraded.";
    } else {
      banner.textContent = "Local Phase15 execution evidence validated. This browser remains read-only and does not refresh brokers/providers automatically.";
    }
  }

  const state = paperById("paper-state");
  if (state) {
    state.textContent = status;
    state.className = `metric compact-metric ${paperStatusClass(status)}`;
  }
  const stateDetail = paperById("paper-state-detail");
  if (stateDetail) stateDetail.textContent = `Updated ${paperTime(payload.generated_at_utc)}`;

  const marketData = paperById("paper-market-data");
  if (marketData) marketData.textContent = "Independent feed";
  const marketDetail = paperById("paper-market-data-detail");
  if (marketDetail) marketDetail.textContent = "See market-input checklist above for realtime/delay/freshness. Feed changes do not imply broker changes.";

  const manifest = payload.manifest || {};
  const routing = paperById("paper-routing");
  if (routing) routing.textContent = manifest.selected_broker ? `${String(manifest.selected_broker).toUpperCase()} · ${String(manifest.selected_environment || "unknown").toUpperCase()}` : "Not selected";
  const routingDetail = paperById("paper-routing-detail");
  if (routingDetail) routingDetail.textContent = manifest.requires_reconciliation ? "Reconciliation required before further execution." : "Execution broker is separate from market-data source.";

  const account = payload.account || null;
  const accountMetric = paperById("paper-account");
  if (accountMetric) accountMetric.textContent = account ? paperMoney(account.equity) : "Unavailable";
  const accountDetail = paperById("paper-account-detail");
  if (accountDetail) {
    accountDetail.textContent = account
      ? `${account.snapshot_kind} · cash ${paperMoney(account.cash)} · buying power ${paperMoney(account.buying_power)} · ${paperTime(account.as_of_utc)}`
      : "No hash-verified reconciliation snapshot available.";
  }

  const stats = payload.statistics || {};
  const realized = paperById("paper-realized");
  if (realized) realized.textContent = paperMoney(stats.total_realized_gross_pnl || 0);
  const realizedDetail = paperById("paper-realized-detail");
  if (realizedDetail) realizedDetail.textContent = `Closed ${paperText(stats.closed_trade_count, "0")} · net P&L ${stats.net_realized_pnl_state ? "UNAVAILABLE" : paperMoney(stats.net_realized_pnl)}`;

  const writes = paperById("paper-writes");
  if (writes) {
    const totalWrites = Number(payload.provider_writes || 0) + Number(payload.broker_writes || 0);
    writes.textContent = totalWrites === 0 ? "READ ONLY" : `${totalWrites} writes`;
    writes.className = `metric compact-metric ${totalWrites === 0 ? "state-ok" : "state-danger"}`;
  }
  const writesDetail = paperById("paper-writes-detail");
  if (writesDetail) writesDetail.textContent = `Provider reads ${paperText(payload.provider_reads, "0")} · provider writes ${paperText(payload.provider_writes, "0")} · broker writes ${paperText(payload.broker_writes, "0")}`;

  renderPaperRows(payload);
  renderPaperHealth(payload);
}

async function refreshPaperDashboard() {
  if (paperDashboardState.refreshInFlight || document.hidden) return;
  paperDashboardState.refreshInFlight = true;
  ensurePaperDashboard();
  try {
    const response = await fetch("/api/v1/ops/paper-dashboard", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    renderPaperDashboard(payload);
  } catch (exc) {
    const banner = paperById("paper-dashboard-banner");
    if (banner) {
      banner.className = "banner danger";
      banner.textContent = `Paper dashboard local read failed: ${exc instanceof Error ? exc.message : String(exc)}`;
    }
  } finally {
    paperDashboardState.refreshInFlight = false;
  }
}

window.addEventListener("atlas:observability-refreshed", () => {
  refreshPaperDashboard();
});

window.addEventListener("DOMContentLoaded", () => {
  ensurePaperDashboard();
  refreshPaperDashboard();
});

window.refreshPaperDashboard = refreshPaperDashboard;
window.renderPaperDashboard = renderPaperDashboard;
