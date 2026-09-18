"use strict";

const simulationLifecycleDashboardState = {
  refreshInFlight: false,
};

function lifecycleById(id) {
  return document.getElementById(id);
}

function lifecycleClear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function lifecycleText(value, fallback = "—") {
  return value === null || value === undefined || value === ""
    ? fallback
    : String(value);
}

function lifecycleMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Unavailable";
  }
  return Number(value).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
  });
}

function lifecyclePercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Unavailable";
  }
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function lifecycleNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

function lifecycleTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function lifecycleAge(startValue, endValue) {
  if (!startValue) return "Unavailable";
  const start = new Date(startValue);
  const end = endValue ? new Date(endValue) : new Date();
  if (
    Number.isNaN(start.getTime()) ||
    Number.isNaN(end.getTime()) ||
    end < start
  ) {
    return "Unavailable";
  }
  const totalMinutes = Math.floor((end.getTime() - start.getTime()) / 60000);
  if (totalMinutes < 60) return `${totalMinutes}m`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours < 24) return `${hours}h ${minutes}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function lifecycleHold(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
    return "—";
  }
  const totalMinutes = Math.floor(Number(seconds) / 60);
  if (totalMinutes < 60) return `${totalMinutes}m`;
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours < 24) return `${hours}h ${minutes}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function lifecycleStatusClass(status) {
  const value = String(status || "").toUpperCase();
  if (value === "AVAILABLE") return "state-ok";
  if (value === "INVALID") return "state-danger";
  return "state-warn";
}

function lifecycleCell(text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = lifecycleText(text);
  if (className) cell.className = className;
  return cell;
}

function lifecycleCard(labelText, metricId, detailId) {
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

function lifecycleTableCard(
  eyebrowText,
  titleText,
  emptyId,
  tableId,
  bodyId,
  headers
) {
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
  const row = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    row.appendChild(th);
  });
  thead.appendChild(row);

  const body = document.createElement("tbody");
  body.id = bodyId;
  table.append(thead, body);
  wrap.appendChild(table);
  article.append(title, empty, wrap);
  return article;
}

function ensureSimulationLifecycleDashboard() {
  if (lifecycleById("simulation-lifecycle-dashboard")) return;

  const paper = lifecycleById("paper-dashboard");
  const anchor =
    paper ||
    lifecycleById("phase19-readiness-controls") ||
    lifecycleById("pipeline-stages");
  if (!anchor) return;

  const root = document.createElement("section");
  root.id = "simulation-lifecycle-dashboard";

  const head = document.createElement("section");
  head.className = "section-head";
  const copy = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Track A · Engine-owned simulation lifecycle";
  const title = document.createElement("h2");
  title.textContent = "Simulation lifecycle truth";
  copy.append(eyebrow, title);
  const description = document.createElement("p");
  description.textContent =
    "Read-only projection of accepted simulation closeout and current marked-account state. No browser refresh queries a provider, broker, or legacy execution artifact to reconstruct this truth.";
  head.append(copy, description);

  const banner = document.createElement("section");
  banner.id = "simulation-lifecycle-banner";
  banner.className = "banner warning";
  banner.setAttribute("aria-live", "polite");
  banner.textContent = "Loading engine-owned simulation lifecycle state…";

  const summary = document.createElement("section");
  summary.className = "grid summary-grid";
  summary.setAttribute("aria-label", "Simulation lifecycle summary");
  summary.append(
    lifecycleCard("Lifecycle state", "simulation-lifecycle-state", "simulation-lifecycle-state-detail"),
    lifecycleCard("Marked equity", "simulation-lifecycle-marked-equity", "simulation-lifecycle-marked-detail"),
    lifecycleCard("Book equity", "simulation-lifecycle-book-equity", "simulation-lifecycle-book-detail"),
    lifecycleCard("Realized net P&L", "simulation-lifecycle-realized", "simulation-lifecycle-realized-detail"),
    lifecycleCard("Unrealized P&L", "simulation-lifecycle-unrealized", "simulation-lifecycle-unrealized-detail"),
    lifecycleCard("Mutation authority", "simulation-lifecycle-writes", "simulation-lifecycle-writes-detail")
  );

  const positions = lifecycleTableCard(
    "Current post-close marked positions",
    "Open simulation positions",
    "simulation-lifecycle-positions-empty",
    "simulation-lifecycle-positions-table",
    "simulation-lifecycle-positions-body",
    [
      "Ticker",
      "Kind",
      "Direction",
      "Qty",
      "Entry",
      "Mark",
      "Unrealized",
      "Age",
      "Candidate",
      "State",
    ]
  );

  const closed = lifecycleTableCard(
    "Deterministic closed-trade ledger",
    "Closed simulation trades",
    "simulation-lifecycle-closed-empty",
    "simulation-lifecycle-closed-table",
    "simulation-lifecycle-closed-body",
    [
      "Closed",
      "Ticker",
      "Kind",
      "Direction",
      "Qty",
      "Entry",
      "Exit",
      "Fees",
      "Account realized",
      "Lifetime net",
      "Hold",
    ]
  );

  const provenance = document.createElement("section");
  provenance.className = "card readiness-controls-card";
  const provenanceHead = document.createElement("div");
  provenanceHead.className = "readiness-control-header";
  const provenanceCopy = document.createElement("div");
  const provenanceEyebrow = document.createElement("div");
  provenanceEyebrow.className = "eyebrow";
  provenanceEyebrow.textContent = "Fingerprint-bound source";
  const provenanceTitle = document.createElement("h3");
  provenanceTitle.textContent = "Lifecycle provenance and authority";
  const provenanceDescription = document.createElement("p");
  provenanceDescription.className = "muted";
  provenanceDescription.textContent =
    "The browser displays the injected engine objects only. State and ledger fingerprints, complete mark coverage, and zero mutation authority remain visible.";
  provenanceCopy.append(
    provenanceEyebrow,
    provenanceTitle,
    provenanceDescription
  );
  const provenanceMetric = document.createElement("div");
  provenanceMetric.id = "simulation-lifecycle-health-state";
  provenanceMetric.className = "metric compact-metric";
  provenanceMetric.textContent = "Loading…";
  provenanceHead.append(provenanceCopy, provenanceMetric);

  const provenanceList = document.createElement("div");
  provenanceList.id = "simulation-lifecycle-health-list";
  provenanceList.className = "readiness-checklist";
  provenance.append(provenanceHead, provenanceList);

  root.append(head, banner, summary, positions, closed, provenance);

  if (paper) {
    paper.insertAdjacentElement("afterend", root);
  } else {
    anchor.insertAdjacentElement("afterend", root);
  }
}

function renderSimulationLifecycleRows(payload) {
  const positions = Array.isArray(payload.open_positions)
    ? payload.open_positions
    : [];
  const positionBody = lifecycleById("simulation-lifecycle-positions-body");
  lifecycleClear(positionBody);

  positions.forEach((item) => {
    const row = document.createElement("tr");
    const unrealized =
      item.unrealized_pnl_dollars === null ||
      item.unrealized_pnl_dollars === undefined
        ? "Unavailable"
        : `${lifecycleMoney(item.unrealized_pnl_dollars)} · ${lifecyclePercent(item.unrealized_return)}`;
    row.append(
      lifecycleCell(item.ticker),
      lifecycleCell(item.instrument_kind),
      lifecycleCell(item.direction),
      lifecycleCell(
        `${lifecycleNumber(item.quantity, 4)} ${lifecycleText(item.quantity_unit, "")}`
      ),
      lifecycleCell(lifecycleMoney(item.entry_price_per_unit)),
      lifecycleCell(lifecycleMoney(item.selected_mark_price_per_unit)),
      lifecycleCell(unrealized),
      lifecycleCell(lifecycleAge(item.opened_utc, item.valuation_utc)),
      lifecycleCell(item.candidate_identifier),
      lifecycleCell(item.position_state, "state-ok")
    );
    if (positionBody) positionBody.appendChild(row);
  });

  const positionTable = lifecycleById("simulation-lifecycle-positions-table");
  const positionEmpty = lifecycleById("simulation-lifecycle-positions-empty");
  if (positionTable) positionTable.hidden = positions.length === 0;
  if (positionEmpty) {
    positionEmpty.hidden = positions.length > 0;
    positionEmpty.textContent =
      String(payload.status || "").toUpperCase() === "NOT_CONNECTED"
        ? "No engine-owned lifecycle source is connected to the control-plane projection."
        : "No open simulation positions remain.";
  }

  const closed = Array.isArray(payload.closed_trades)
    ? payload.closed_trades
    : [];
  const closedBody = lifecycleById("simulation-lifecycle-closed-body");
  lifecycleClear(closedBody);

  closed.forEach((item) => {
    const row = document.createElement("tr");
    const totalFees =
      Number(item.entry_fees_dollars || 0) +
      Number(item.exit_fees_dollars || 0);
    row.append(
      lifecycleCell(lifecycleTime(item.exited_utc)),
      lifecycleCell(item.ticker),
      lifecycleCell(item.instrument_kind),
      lifecycleCell(item.direction),
      lifecycleCell(
        `${lifecycleNumber(item.quantity, 4)} ${lifecycleText(item.quantity_unit, "")}`
      ),
      lifecycleCell(lifecycleMoney(item.entry_price_per_unit)),
      lifecycleCell(lifecycleMoney(item.exit_price_per_unit)),
      lifecycleCell(lifecycleMoney(totalFees)),
      lifecycleCell(lifecycleMoney(item.account_realized_pnl_delta_dollars)),
      lifecycleCell(lifecycleMoney(item.lifetime_trade_net_pnl_dollars)),
      lifecycleCell(lifecycleHold(item.hold_seconds))
    );
    if (closedBody) closedBody.appendChild(row);
  });

  const closedTable = lifecycleById("simulation-lifecycle-closed-table");
  const closedEmpty = lifecycleById("simulation-lifecycle-closed-empty");
  if (closedTable) closedTable.hidden = closed.length === 0;
  if (closedEmpty) {
    closedEmpty.hidden = closed.length > 0;
    closedEmpty.textContent = "No deterministic simulation closeouts are recorded.";
  }
}

function renderSimulationLifecycleHealth(payload) {
  const health = payload.health || {};
  const source = payload.source || {};
  const authority = payload.authority || {};
  const metric = lifecycleById("simulation-lifecycle-health-state");
  if (metric) {
    metric.textContent = payload.status || "UNAVAILABLE";
    metric.className = `metric compact-metric ${lifecycleStatusClass(payload.status)}`;
  }

  const root = lifecycleById("simulation-lifecycle-health-list");
  lifecycleClear(root);
  if (!root) return;

  const checks = [
    [
      "Engine lifecycle source connected",
      health.engine_source_connected === true,
      health.engine_source_connected === true
        ? "Connected"
        : health.reason || "Not connected",
    ],
    [
      "Source validation",
      health.source_valid === true,
      health.source_valid === true ? "Fingerprint-valid" : "Unavailable",
    ],
    [
      "Complete mark coverage",
      health.complete_mark_coverage === true,
      health.complete_mark_coverage === true ? "Complete" : "Unavailable",
    ],
    [
      "Automatic provider refresh",
      health.automatic_provider_refresh === false,
      health.automatic_provider_refresh === false ? "Disabled" : "Not proven disabled",
    ],
    [
      "Automatic broker refresh",
      health.automatic_broker_refresh === false,
      health.automatic_broker_refresh === false ? "Disabled" : "Not proven disabled",
    ],
    [
      "Browser mutation authority",
      authority.browser_mutation_authority === false,
      authority.browser_mutation_authority === false ? "Disabled" : "Not proven disabled",
    ],
    [
      "PAPER authority",
      authority.paper_authority === false,
      authority.paper_authority === false ? "False" : "Not proven false",
    ],
    [
      "LIVE authority",
      authority.live_authority === false,
      authority.live_authority === false ? "False" : "Not proven false",
    ],
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

  if (source.closeout_state_fingerprint) {
    const provenance = document.createElement("div");
    provenance.className = "readiness-check readiness-authority-reminder";
    const icon = document.createElement("span");
    icon.className = "readiness-check-icon";
    icon.textContent = "i";
    const label = document.createElement("span");
    label.textContent =
      `Book ${lifecycleTime(source.book_as_of_utc)} · valuation ${lifecycleTime(source.valuation_utc)} · closeout ${String(source.closeout_state_fingerprint).slice(0, 12)}… · marked ${String(source.marked_state_fingerprint || "").slice(0, 12)}…`;
    provenance.append(icon, label);
    root.appendChild(provenance);
  }
}

function renderSimulationLifecycleDashboard(payload) {
  ensureSimulationLifecycleDashboard();

  const status = String(payload.status || "UNAVAILABLE").toUpperCase();
  const banner = lifecycleById("simulation-lifecycle-banner");
  if (banner) {
    banner.className = `banner ${status === "INVALID" ? "danger" : status === "AVAILABLE" ? "success" : "warning"}`;
    if (status === "NOT_CONNECTED") {
      banner.textContent =
        "The lifecycle projection is installed, but no engine-owned simulation source is injected yet. No legacy artifact or broker state is being substituted.";
    } else if (status === "INVALID") {
      banner.textContent =
        "Injected lifecycle state failed fingerprint or lineage validation. The browser will not display it as trading truth.";
    } else {
      banner.textContent =
        "Engine-owned simulation lifecycle state validated. This projection is read-only and does not refresh providers or brokers.";
    }
  }

  const stateMetric = lifecycleById("simulation-lifecycle-state");
  if (stateMetric) {
    stateMetric.textContent = status;
    stateMetric.className = `metric compact-metric ${lifecycleStatusClass(status)}`;
  }
  const stateDetail = lifecycleById("simulation-lifecycle-state-detail");
  if (stateDetail) {
    stateDetail.textContent = `Updated ${lifecycleTime(payload.generated_at_utc)}`;
  }

  const account = payload.account || null;
  const markedMetric = lifecycleById("simulation-lifecycle-marked-equity");
  if (markedMetric) {
    markedMetric.textContent = account
      ? lifecycleMoney(account.marked_equity)
      : "Unavailable";
  }
  const markedDetail = lifecycleById("simulation-lifecycle-marked-detail");
  if (markedDetail) {
    markedDetail.textContent = account
      ? `Marked open value ${lifecycleMoney(account.marked_open_position_value_dollars)}`
      : "No validated lifecycle state.";
  }

  const bookMetric = lifecycleById("simulation-lifecycle-book-equity");
  if (bookMetric) {
    bookMetric.textContent = account
      ? lifecycleMoney(account.account_book_equity)
      : "Unavailable";
  }
  const bookDetail = lifecycleById("simulation-lifecycle-book-detail");
  if (bookDetail) {
    bookDetail.textContent = account
      ? `Cash ${lifecycleMoney(account.cash)} · open book ${lifecycleMoney(account.open_entry_book_value_dollars)}`
      : "No validated lifecycle state.";
  }

  const realizedMetric = lifecycleById("simulation-lifecycle-realized");
  if (realizedMetric) {
    realizedMetric.textContent = account
      ? lifecycleMoney(account.cumulative_lifetime_trade_net_pnl_dollars)
      : "Unavailable";
  }
  const realizedDetail = lifecycleById("simulation-lifecycle-realized-detail");
  if (realizedDetail) {
    realizedDetail.textContent = account
      ? `Account realized ${lifecycleMoney(account.cumulative_account_realized_pnl_dollars)} · entry fees ${lifecycleMoney(account.cumulative_entry_fees_dollars)} · exit fees ${lifecycleMoney(account.cumulative_exit_fees_dollars)}`
      : "No validated lifecycle state.";
  }

  const unrealizedMetric = lifecycleById("simulation-lifecycle-unrealized");
  if (unrealizedMetric) {
    unrealizedMetric.textContent = account
      ? lifecycleMoney(account.aggregate_unrealized_pnl_dollars)
      : "Unavailable";
  }
  const unrealizedDetail = lifecycleById("simulation-lifecycle-unrealized-detail");
  if (unrealizedDetail) {
    const stats = payload.statistics || {};
    unrealizedDetail.textContent = account
      ? `Open ${lifecycleText(stats.open_position_count, "0")} · closed ${lifecycleText(stats.closed_trade_count, "0")}`
      : "No validated lifecycle state.";
  }

  const writes = lifecycleById("simulation-lifecycle-writes");
  if (writes) {
    const totalWrites =
      Number(payload.provider_writes || 0) +
      Number(payload.broker_writes || 0) +
      Number(payload.order_writes || 0);
    writes.textContent = totalWrites === 0 ? "READ ONLY" : `${totalWrites} writes`;
    writes.className = `metric compact-metric ${totalWrites === 0 ? "state-ok" : "state-danger"}`;
  }
  const writesDetail = lifecycleById("simulation-lifecycle-writes-detail");
  if (writesDetail) {
    writesDetail.textContent =
      `Provider reads ${lifecycleText(payload.provider_reads, "0")} · broker reads ${lifecycleText(payload.broker_reads, "0")} · provider/broker/order writes 0`;
  }

  renderSimulationLifecycleRows(payload);
  renderSimulationLifecycleHealth(payload);
}

async function refreshSimulationLifecycleDashboard() {
  if (simulationLifecycleDashboardState.refreshInFlight || document.hidden) {
    return;
  }
  simulationLifecycleDashboardState.refreshInFlight = true;
  ensureSimulationLifecycleDashboard();

  try {
    const response = await fetch("/api/v1/ops/simulation-lifecycle", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    renderSimulationLifecycleDashboard(payload);
  } catch (exc) {
    const banner = lifecycleById("simulation-lifecycle-banner");
    if (banner) {
      banner.className = "banner danger";
      banner.textContent =
        `Simulation lifecycle local read failed: ${exc instanceof Error ? exc.message : String(exc)}`;
    }
  } finally {
    simulationLifecycleDashboardState.refreshInFlight = false;
  }
}

window.addEventListener("atlas:observability-refreshed", () => {
  refreshSimulationLifecycleDashboard();
});

window.addEventListener("DOMContentLoaded", () => {
  ensureSimulationLifecycleDashboard();
  refreshSimulationLifecycleDashboard();
});

window.refreshSimulationLifecycleDashboard =
  refreshSimulationLifecycleDashboard;
window.renderSimulationLifecycleDashboard =
  renderSimulationLifecycleDashboard;
