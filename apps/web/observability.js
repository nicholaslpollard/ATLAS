"use strict";

const obsStyle = document.createElement("link");
obsStyle.rel = "stylesheet";
obsStyle.href = "/assets/observability.css";
document.head.appendChild(obsStyle);

const obsById = (id) => document.getElementById(id);
let obsCandidateRows = [];
let obsCandidatesAvailable = false;

function obsText(id, value) {
  const node = obsById(id);
  if (node) node.textContent = value == null || value === "" ? "—" : String(value);
}

function obsClear(node) {
  while (node && node.firstChild) node.removeChild(node.firstChild);
}

function obsState(value) {
  const normalized = String(value || "").toUpperCase();
  if (["AVAILABLE", "ACCEPTED", "COMPLETE", "HEALTHY", "PROMOTED", "STACKED_PREP_GREEN", "RECENT", "INPUTS_APPEAR_READY", "SUBSCRIBED", "REALTIME", "FRESH", "ADMITTED"].includes(normalized)) return "state-ok";
  if (["STACKED_PREP", "WAITING_EXTERNAL", "WARM", "CAUTIOUS", "OLDER", "CONNECTING", "CONNECTED", "AUTHENTICATED", "RESEARCH", "NOT_RUN"].includes(normalized)) return "state-warn";
  if (["UNAVAILABLE", "BLOCKED", "ERROR", "REJECT", "REJECTED", "NOT_READY", "STOPPED", "DEGRADED", "DISCONNECTED", "STALE"].includes(normalized)) return "state-danger";
  return "state-muted";
}

function obsPercent(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : "—";
}

function obsMoney(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

function obsAge(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "age unknown";
  if (n < 1) return `${Math.round(n * 60)}m old`;
  if (n < 48) return `${n.toFixed(1)}h old`;
  return `${(n / 24).toFixed(1)}d old`;
}

function obsSecondsAge(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "age unknown";
  if (n < 60) return `${n.toFixed(0)}s old`;
  if (n < 3600) return `${(n / 60).toFixed(1)}m old`;
  return `${(n / 3600).toFixed(1)}h old`;
}

function obsDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

async function obsGetJson(path) {
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

function renderPhase(payload) {
  const phase = payload.phase || {};
  const authority = payload.authority || {};
  obsText("obs-phase", `Phase ${phase.stacked_phase || "19"} · ${phase.stacked_phase_state || "STACKED_PREP"}`);
  const badge = obsById("obs-phase");
  if (badge) badge.className = `metric ${obsState(phase.stacked_phase_state)}`;
  obsText(
    "obs-phase-detail",
    `${phase.stacked_phase_name || "Operations Dashboard & Paper/Shadow Observability"} · upstream Phase ${phase.merge_authoritative_phase || "18B"} ${phase.merge_authoritative_state || ""}`
  );
  obsText("obs-authority", authority.mode || "READ_ONLY_LOCAL_ARTIFACT_OBSERVABILITY");
  obsText(
    "obs-authority-detail",
    `provider reads ${authority.provider_reads ?? 0} · provider writes ${authority.provider_writes ?? 0} · live ${authority.live_execution_promoted ? "enabled" : "disabled"}`
  );
}

function renderArtifactRecency(payload) {
  const recency = payload.artifact_recency || {};
  const candidate = recency.candidate_materialization || {};
  const ai = recency.ai_audit || {};
  const candidateState = candidate.state || "UNKNOWN";
  const aiState = ai.state || "UNKNOWN";
  const node = obsById("artifact-recency");
  const overall = candidateState === "RECENT" && aiState === "RECENT"
    ? "RECENT"
    : candidateState === "OLDER" || aiState === "OLDER"
      ? "OLDER"
      : "UNKNOWN";
  obsText("artifact-recency", overall);
  if (node) node.className = `metric ${obsState(overall)}`;
  obsText(
    "artifact-recency-detail",
    `Candidate ${candidateState} (${obsAge(candidate.age_hours)}) · AI ${aiState} (${obsAge(ai.age_hours)}) · diagnostic only`
  );
}

function renderPipeline(payload) {
  const root = obsById("pipeline-stages");
  obsClear(root);
  const pipeline = payload.pipeline || {};
  const stages = [
    ["Live market state", pipeline.live_market_state, "Persisted Phase 5 state · no socket started by dashboard"],
    ["Candidate intelligence", pipeline.candidate_materialization, "Discovery · regime · ML · strategy"],
    ["Independent AI audit", pipeline.ai_audit, "Phase 14 review evidence"],
    ["Execution outcomes", pipeline.execution_outcomes, "Phase 15 descriptive outcomes"],
  ];
  stages.forEach(([name, stage, detail]) => {
    const card = document.createElement("article");
    card.className = "card pipeline-card";
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = name;
    const value = document.createElement("div");
    const available = Boolean(stage && stage.available);
    value.className = `metric ${available ? "state-ok" : "state-muted"}`;
    value.textContent = available ? "Available" : "No artifact";
    const meta = document.createElement("div");
    meta.className = "muted";
    const count = stage && stage.count != null ? ` · ${stage.count} records` : "";
    const asOf = stage && stage.as_of_date ? ` · ${stage.as_of_date}` : "";
    const recency = stage && stage.recency_state ? ` · ${stage.recency_state} (${obsAge(stage.age_hours)})` : "";
    const inputState = stage && stage.phase18_input_state ? ` · ${stage.phase18_input_state}` : "";
    meta.textContent = `${detail}${count}${asOf}${recency}${inputState}`;
    card.append(label, value, meta);
    root.appendChild(card);
  });
}

function ensureLiveMarketPanel() {
  if (obsById("live-market-panel")) return;
  const pipeline = obsById("pipeline-stages");
  if (!pipeline) return;

  const head = document.createElement("section");
  head.className = "section-head live-market-head";
  const titleWrap = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Realtime readiness inputs";
  const title = document.createElement("h2");
  title.textContent = "Local live-market state";
  titleWrap.append(eyebrow, title);
  const description = document.createElement("p");
  description.textContent = "Read-only display of the persisted Phase 5 market-state snapshot. This panel never opens a market-data connection and does not authorize Phase 18 mutation.";
  head.append(titleWrap, description);

  const panel = document.createElement("section");
  panel.id = "live-market-panel";
  panel.className = "grid live-market-grid";
  [
    ["Phase 18 market inputs", "live-input-state"],
    ["Connection", "live-connection"],
    ["Feed", "live-feed"],
    ["Session", "live-session"],
    ["Snapshot age", "live-snapshot-age"],
    ["Events", "live-events"],
  ].forEach(([labelText, id]) => {
    const card = document.createElement("article");
    card.className = "card";
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = labelText;
    const value = document.createElement("div");
    value.id = id;
    value.className = "metric compact-metric";
    value.textContent = "—";
    card.append(label, value);
    panel.appendChild(card);
  });

  const quoteCard = document.createElement("section");
  quoteCard.id = "live-quotes-card";
  quoteCard.className = "card table-card live-quotes-card";
  const empty = document.createElement("div");
  empty.id = "live-quotes-empty";
  empty.className = "empty";
  empty.textContent = "No focused quotes in the persisted live-state snapshot.";
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const table = document.createElement("table");
  table.id = "live-quotes-table";
  table.hidden = true;
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["Ticker", "Freshness", "Bid", "Ask", "Session", "Feed", "Provider time", "Received"].forEach((text) => {
    const th = document.createElement("th");
    th.textContent = text;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  const tbody = document.createElement("tbody");
  tbody.id = "live-quotes-body";
  table.append(thead, tbody);
  wrap.appendChild(table);
  quoteCard.append(empty, wrap);

  pipeline.insertAdjacentElement("afterend", quoteCard);
  pipeline.insertAdjacentElement("afterend", panel);
  pipeline.insertAdjacentElement("afterend", head);
}

function renderLiveMarket(payload) {
  ensureLiveMarketPanel();
  const live = payload.live_market || {};
  const inputs = live.phase18_market_inputs || {};
  const session = live.session || {};
  const inputState = inputs.state || "UNAVAILABLE";
  obsText("live-input-state", inputState);
  const inputNode = obsById("live-input-state");
  if (inputNode) inputNode.className = `metric compact-metric ${obsState(inputState)}`;
  obsText("live-connection", live.connection_state || "UNAVAILABLE");
  const connectionNode = obsById("live-connection");
  if (connectionNode) connectionNode.className = `metric compact-metric ${obsState(live.connection_state)}`;
  obsText("live-feed", live.feed_mode ? `${String(live.feed_mode).toUpperCase()} · delay ${live.expected_delay_seconds ?? "—"}s` : "UNAVAILABLE");
  obsText("live-session", session.session_segment ? `${String(session.session_segment).toUpperCase()} · ${session.local_date || "—"}` : "UNAVAILABLE");
  obsText("live-snapshot-age", live.available ? obsSecondsAge(live.snapshot_age_seconds) : "UNAVAILABLE");
  obsText("live-events", `${live.accepted_events ?? 0} accepted / ${live.received_events ?? 0} received · ${live.parse_errors ?? 0} parse errors · ${live.reconnects ?? 0} reconnects`);

  const empty = obsById("live-quotes-empty");
  const table = obsById("live-quotes-table");
  const body = obsById("live-quotes-body");
  obsClear(body);
  const rows = Array.isArray(live.quotes) ? live.quotes : [];
  if (rows.length === 0) {
    if (empty) {
      empty.hidden = false;
      empty.textContent = live.available
        ? "No focused quotes in the persisted live-state snapshot."
        : "Live market state is unavailable. Start the accepted market-state service separately when live evidence is needed.";
    }
    if (table) table.hidden = true;
    return;
  }
  if (empty) empty.hidden = true;
  if (table) table.hidden = false;
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    [
      item.ticker || "—",
      String(item.quote_freshness || "unknown").toUpperCase(),
      item.bid_price == null ? "—" : Number(item.bid_price).toFixed(2),
      item.ask_price == null ? "—" : Number(item.ask_price).toFixed(2),
      String(item.session_segment || "—").toUpperCase(),
      String(item.feed_mode || "—").toUpperCase(),
      obsDateTime(item.provider_timestamp_utc),
      obsDateTime(item.received_at_utc),
    ].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 1) td.className = obsState(value);
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function candidateMatchesFilters(item) {
  const query = String(obsById("candidate-search")?.value || "").trim().toUpperCase();
  const state = String(obsById("candidate-state-filter")?.value || "ALL").toUpperCase();
  const promotedOnly = Boolean(obsById("candidate-promoted-only")?.checked);
  const ticker = String(item.ticker || "").toUpperCase();
  const itemState = String(item.discovery_state || "").toUpperCase();
  if (query && !ticker.includes(query)) return false;
  if (state !== "ALL" && itemState !== state) return false;
  if (promotedOnly && !item.promoted) return false;
  return true;
}

function showCandidateDetail(item) {
  obsText("candidate-detail-ticker", item.ticker);
  obsText("candidate-detail-date", item.as_of_date);
  obsText("candidate-detail-discovery", String(item.discovery_state || "—").toUpperCase());
  obsText("candidate-detail-direction", item.direction);
  obsText("candidate-detail-priority", Number.isFinite(Number(item.priority_score)) ? Number(item.priority_score).toFixed(3) : "—");
  obsText("candidate-detail-market", item.market_state);
  obsText("candidate-detail-sector", item.sector_state);
  obsText("candidate-detail-ticker-regime", item.ticker_state);
  obsText("candidate-detail-p-up", obsPercent(item.p_up));
  obsText("candidate-detail-p-neutral", obsPercent(item.p_neutral));
  obsText("candidate-detail-p-down", obsPercent(item.p_down));
  obsText("candidate-detail-model", item.ml_model_id);
  obsText(
    "candidate-detail-strategies",
    Array.isArray(item.supported_fired_strategy_ids) && item.supported_fired_strategy_ids.length
      ? item.supported_fired_strategy_ids.join(", ")
      : "None"
  );
  obsText("candidate-detail-promotion", item.promoted ? "PROMOTED" : "Not promoted");
  obsText(
    "candidate-detail-reasons",
    Array.isArray(item.reason_codes) && item.reason_codes.length ? item.reason_codes.join(", ") : "None"
  );
  const dialog = obsById("candidate-dialog");
  if (dialog && typeof dialog.showModal === "function") dialog.showModal();
}

function renderCandidateRows() {
  const empty = obsById("candidates-empty");
  const table = obsById("candidates-table");
  const body = obsById("candidates-body");
  obsClear(body);
  const rows = obsCandidateRows.filter(candidateMatchesFilters);
  obsText("candidate-visible-count", rows.length);

  if (!obsCandidatesAvailable || obsCandidateRows.length === 0) {
    if (empty) {
      empty.hidden = false;
      empty.textContent = obsCandidatesAvailable
        ? "No WARM/HOT directional candidates in the current materialization."
        : "Candidate artifacts are not currently available. ATLAS does not synthesize missing evidence.";
    }
    if (table) table.hidden = true;
    return;
  }

  if (rows.length === 0) {
    if (empty) {
      empty.hidden = false;
      empty.textContent = "No candidates match the current dashboard filters.";
    }
    if (table) table.hidden = true;
    return;
  }

  if (empty) empty.hidden = true;
  if (table) table.hidden = false;
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    const values = [
      item.ticker || "—",
      String(item.discovery_state || "—").toUpperCase(),
      String(item.direction || "—"),
      Number.isFinite(Number(item.priority_score)) ? Number(item.priority_score).toFixed(3) : "—",
      item.market_state || "—",
      item.ticker_state || "—",
      obsPercent(item.p_up),
      obsPercent(item.p_down),
      item.promoted ? "PROMOTED" : "Not promoted",
    ];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 1 || index === 8) td.className = obsState(value);
      tr.appendChild(td);
    });
    const inspectCell = document.createElement("td");
    const inspect = document.createElement("button");
    inspect.type = "button";
    inspect.className = "compact-button";
    inspect.textContent = "Inspect";
    inspect.addEventListener("click", () => showCandidateDetail(item));
    inspectCell.appendChild(inspect);
    tr.appendChild(inspectCell);
    body.appendChild(tr);
  });
}

function renderCandidates(payload) {
  const summary = payload.candidates || {};
  obsText("candidate-date", summary.as_of_date || "No current artifact");
  obsText("candidate-date-summary", summary.as_of_date || "No current artifact");
  obsText("candidate-count", summary.considered_count ?? 0);
  obsText("candidate-promoted", summary.promoted_count ?? 0);
  obsText("candidate-promoted-summary", summary.promoted_count ?? 0);
  obsText("candidate-model", summary.accepted_ml_model_id || "—");
  obsText(
    "candidate-generated",
    summary.generated_at_utc
      ? `Generated ${obsDateTime(summary.generated_at_utc)} · ${summary.recency_state || "UNKNOWN"} · ${obsAge(summary.age_hours)}`
      : "Exact persisted materialization only."
  );
  obsCandidatesAvailable = Boolean(summary.available);
  obsCandidateRows = Array.isArray(summary.candidates) ? summary.candidates : [];
  renderCandidateRows();
}

function renderAi(payload) {
  const ai = payload.ai_audit || {};
  const dispositions = ai.disposition_counts || {};
  obsText("ai-date", ai.as_of_date || "No current artifact");
  obsText("ai-count", ai.review_count ?? 0);
  obsText("ai-approve", dispositions.APPROVE ?? 0);
  obsText("ai-cautious", dispositions.CAUTIOUS ?? 0);
  obsText("ai-reject", dispositions.REJECT ?? 0);
  obsText(
    "ai-detail",
    ai.available
      ? `${ai.no_review_disposition || "Independent review evidence available"} · ${ai.recency_state || "UNKNOWN"} · ${obsAge(ai.age_hours)}`
      : "AI review artifacts are not currently available; no review is inferred."
  );
}

function renderOutcomes(payload) {
  const outcomes = payload.outcomes || {};
  obsText("outcome-count", outcomes.outcome_count ?? 0);
  obsText("outcome-pnl", obsMoney(outcomes.total_gross_pnl));
  obsText("outcome-win-rate", obsPercent(outcomes.win_rate));
  obsText(
    "outcome-record",
    `${outcomes.winning_count ?? 0} W · ${outcomes.losing_count ?? 0} L · ${outcomes.flat_count ?? 0} flat`
  );
  obsText(
    "outcome-average-r",
    outcomes.average_realized_r == null ? "—" : Number(outcomes.average_realized_r).toFixed(2)
  );
  obsText("outcome-latest", obsDateTime(outcomes.latest_closed_at_utc));

  const empty = obsById("outcomes-empty");
  const table = obsById("outcomes-table");
  const body = obsById("outcomes-body");
  obsClear(body);
  const rows = Array.isArray(outcomes.outcomes) ? outcomes.outcomes : [];
  if (rows.length === 0) {
    if (empty) empty.hidden = false;
    if (table) table.hidden = true;
    return;
  }
  if (empty) empty.hidden = true;
  if (table) table.hidden = false;
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    [
      item.ticker || "—",
      item.broker || "—",
      item.direction || "—",
      item.exit_reason || "—",
      obsMoney(item.gross_pnl),
      obsPercent(item.gross_return),
      item.realized_r == null ? "—" : Number(item.realized_r).toFixed(2),
      obsDateTime(item.closed_at_utc),
    ].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function renderReferenceLab(catalog, replay) {
  const strategies = Array.isArray(catalog && catalog.strategies) ? catalog.strategies : [];
  const summary = replay && replay.summary;
  obsText("reference-lab-strategies", `${strategies.length} policies`);
  const strategyMetric = obsById("reference-lab-strategies");
  if (strategyMetric) strategyMetric.className = `metric ${strategies.length ? "state-ok" : "state-warn"}`;
  obsText("reference-lab-families", `${catalog && catalog.family_count != null ? catalog.family_count : 0} materially different families`);

  const strategyBody = obsById("reference-lab-strategy-body");
  obsClear(strategyBody);
  strategies.forEach((row) => {
    const specification = row.specification || {};
    const authority = row.authority || {};
    const statistics = summary && summary.summary_by_strategy
      ? summary.summary_by_strategy[specification.strategy_id] || {}
      : null;
    const tr = document.createElement("tr");
    [
      specification.strategy_id || "—",
      specification.family || "—",
      specification.direction || "—",
      statistics ? statistics.signals : "—",
      statistics ? statistics.admitted : "—",
      statistics ? statistics.completed : "—",
      statistics ? obsMoney(statistics.net_pnl) : "—",
      authority.authority || "RESEARCH",
    ].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = String(value);
      if (index === 6 && statistics) td.className = Number(statistics.net_pnl) >= 0 ? "state-ok" : "state-danger";
      if (index === 7) td.className = obsState(value);
      tr.appendChild(td);
    });
    strategyBody.appendChild(tr);
  });

  const status = String((replay && replay.status) || "NOT_RUN");
  const banner = obsById("reference-lab-banner");
  if (banner) {
    banner.className = status === "AVAILABLE" ? "banner ok" : status === "INVALID" ? "banner danger" : "banner warning";
    banner.textContent = replay && replay.message ? replay.message : "Reference replay state is unavailable.";
  }
  const authority = obsById("reference-lab-authority");
  if (authority) authority.className = `metric ${status === "INVALID" ? "state-danger" : "state-warn"}`;
  const integrity = (replay && replay.artifact_integrity) || {};
  const integrityNode = obsById("reference-lab-integrity");
  if (integrityNode) {
    if (integrity.all_sha256_verified) {
      integrityNode.textContent = `${integrity.verified_artifacts}/${integrity.expected_artifacts} replay artifacts SHA-256 verified.`;
      integrityNode.className = "muted state-ok";
    } else if (status === "INVALID") {
      integrityNode.textContent = "Replay artifact validation failed closed.";
      integrityNode.className = "muted state-danger";
    } else {
      integrityNode.textContent = "Replay artifacts not present.";
      integrityNode.className = "muted";
    }
  }

  if (status === "AVAILABLE" && summary) {
    const totalReturn = Number(summary.total_return);
    const drawdown = Number(summary.maximum_drawdown);
    obsText("reference-lab-return", obsPercent(totalReturn));
    const returnNode = obsById("reference-lab-return");
    if (returnNode) returnNode.className = `metric ${totalReturn >= 0 ? "state-ok" : "state-danger"}`;
    obsText("reference-lab-equity", `Final equity ${obsMoney(summary.final_equity)} · costs ${obsMoney(summary.total_transaction_cost)}`);
    obsText("reference-lab-drawdown", obsPercent(drawdown));
    const drawdownNode = obsById("reference-lab-drawdown");
    if (drawdownNode) drawdownNode.className = `metric ${drawdown < -0.1 ? "state-danger" : "state-warn"}`;
    obsText("reference-lab-trades", `${summary.completed_positions || 0} completed · ${summary.admitted_positions || 0} admitted`);
  } else {
    obsText("reference-lab-return", "Not run");
    obsText("reference-lab-equity", "Awaiting trusted-lake DEVELOPMENT replay");
    obsText("reference-lab-drawdown", "Not run");
    obsText("reference-lab-trades", "No account outcomes opened");
    ["reference-lab-return", "reference-lab-drawdown"].forEach((id) => {
      const node = obsById(id);
      if (node) node.className = `metric ${status === "INVALID" ? "state-danger" : "state-warn"}`;
    });
  }

  const outcomes = Array.isArray(replay && replay.recent_position_outcomes)
    ? replay.recent_position_outcomes.slice().reverse()
    : [];
  const empty = obsById("reference-lab-outcomes-empty");
  const table = obsById("reference-lab-outcomes-table");
  const body = obsById("reference-lab-outcomes-body");
  obsClear(body);
  if (empty) empty.hidden = outcomes.length > 0;
  if (table) table.hidden = outcomes.length === 0;
  outcomes.forEach((item) => {
    const tr = document.createElement("tr");
    [
      item.exit_session || "—",
      item.ticker || "—",
      item.family || "—",
      item.strategy_id || "—",
      item.exit_reason || "—",
      obsPercent(item.net_return_on_entry_notional),
      obsMoney(item.net_pnl),
    ].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = String(value);
      if (index === 5 || index === 6) td.className = Number(item.net_pnl) >= 0 ? "state-ok" : "state-danger";
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });

  renderReferenceEquity(replay && replay.equity_curve_tail, summary);
  renderReferenceDecisions(replay && replay.recent_portfolio_decisions);
  renderReferenceOrders(replay && replay.recent_simulated_orders);
}

function renderReferenceEquity(rawPoints, summary) {
  const svg = obsById("reference-lab-equity-chart");
  const empty = obsById("reference-lab-equity-empty");
  const caption = obsById("reference-lab-equity-caption");
  const points = Array.isArray(rawPoints)
    ? rawPoints.filter((row) => row && Number.isFinite(Number(row.equity)))
    : [];
  obsClear(svg);
  obsClear(caption);
  if (!svg || points.length === 0) {
    if (empty) empty.hidden = false;
    if (svg) svg.hidden = true;
    if (caption) caption.hidden = true;
    obsText("reference-lab-equity-latest", "No replay equity recorded.");
    return;
  }

  if (empty) empty.hidden = true;
  svg.hidden = false;
  if (caption) caption.hidden = false;
  const width = 720;
  const height = 210;
  const padding = 18;
  const values = points.map((row) => Number(row.equity));
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || Math.max(Math.abs(maximum) * 0.01, 1);
  const x = (index) => padding + (points.length === 1 ? (width - 2 * padding) / 2 : index * (width - 2 * padding) / (points.length - 1));
  const y = (value) => padding + (maximum - value) * (height - 2 * padding) / span;
  const linePoints = points.map((row, index) => `${x(index).toFixed(2)},${y(Number(row.equity)).toFixed(2)}`);
  const namespace = "http://www.w3.org/2000/svg";
  const baseline = document.createElementNS(namespace, "line");
  baseline.setAttribute("x1", String(padding));
  baseline.setAttribute("x2", String(width - padding));
  baseline.setAttribute("y1", String(height - padding));
  baseline.setAttribute("y2", String(height - padding));
  baseline.setAttribute("class", "reference-chart-baseline");
  svg.appendChild(baseline);
  const area = document.createElementNS(namespace, "polygon");
  area.setAttribute("points", `${x(0)},${height - padding} ${linePoints.join(" ")} ${x(points.length - 1)},${height - padding}`);
  area.setAttribute("class", "reference-chart-area");
  svg.appendChild(area);
  const line = document.createElementNS(namespace, "polyline");
  line.setAttribute("points", linePoints.join(" "));
  line.setAttribute("class", "reference-chart-line");
  svg.appendChild(line);
  const lastPoint = document.createElementNS(namespace, "circle");
  lastPoint.setAttribute("cx", String(x(points.length - 1)));
  lastPoint.setAttribute("cy", String(y(values[values.length - 1])));
  lastPoint.setAttribute("r", "4.5");
  lastPoint.setAttribute("class", "reference-chart-point");
  svg.appendChild(lastPoint);

  const first = points[0];
  const last = points[points.length - 1];
  svg.setAttribute("aria-label", `Closing account equity from ${obsMoney(first.equity)} to ${obsMoney(last.equity)} over ${points.length} displayed sessions`);
  obsText(
    "reference-lab-equity-latest",
    `${last.session || "Latest"} · ${obsMoney(last.equity)} · ${obsPercent(last.gross_exposure_fraction)} gross · ${last.open_positions || 0} open`
  );
  if (caption) {
    [
      `${first.session || "Start"}: ${obsMoney(first.equity)}`,
      `Displayed range ${obsMoney(minimum)}–${obsMoney(maximum)} · last ${Math.min(points.length, 120)} sessions`,
      `${last.session || "End"}: ${obsMoney(last.equity)} · max drawdown ${obsPercent(summary && summary.maximum_drawdown)}`,
    ].forEach((value) => {
      const spanNode = document.createElement("span");
      spanNode.textContent = value;
      caption.appendChild(spanNode);
    });
  }
}

function renderReferenceDecisions(rawRows) {
  const rows = Array.isArray(rawRows) ? rawRows.slice().reverse() : [];
  const empty = obsById("reference-lab-decisions-empty");
  const table = obsById("reference-lab-decisions-table");
  const body = obsById("reference-lab-decisions-body");
  obsClear(body);
  if (empty) empty.hidden = rows.length > 0;
  if (table) table.hidden = rows.length === 0;
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    const reasons = Array.isArray(item.reason_codes) ? item.reason_codes.join(" · ") : "—";
    [
      item.requested_entry_session || item.signal_session || "—",
      item.ticker || "—",
      item.family || "—",
      item.status || "—",
      item.admitted_quantity == null ? "—" : item.admitted_quantity,
      item.admitted_notional == null ? "—" : obsMoney(item.admitted_notional),
      reasons,
    ].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = String(value);
      if (index === 3) td.className = obsState(value);
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function renderReferenceOrders(rawRows) {
  const rows = Array.isArray(rawRows) ? rawRows.slice().reverse() : [];
  const empty = obsById("reference-lab-orders-empty");
  const table = obsById("reference-lab-orders-table");
  const body = obsById("reference-lab-orders-body");
  obsClear(body);
  if (empty) empty.hidden = rows.length > 0;
  if (table) table.hidden = rows.length === 0;
  rows.forEach((item) => {
    const tr = document.createElement("tr");
    [
      item.session || "—",
      item.ticker || "—",
      item.kind || "—",
      item.timing || "—",
      item.quantity == null ? "—" : item.quantity,
      obsMoney(item.price),
      obsMoney(item.transaction_cost),
      obsMoney(item.cash_after),
    ].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = String(value);
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

function renderObservability(payload) {
  renderPhase(payload);
  renderArtifactRecency(payload);
  renderPipeline(payload);
  renderLiveMarket(payload);
  renderCandidates(payload);
  renderAi(payload);
  renderOutcomes(payload);
  obsText("obs-updated", obsDateTime(payload.generated_at_utc));
}

async function loadObservability() {
  const error = obsById("observability-error");
  if (error) {
    error.hidden = true;
    error.textContent = "";
  }
  try {
    const [payload, catalog, replay] = await Promise.all([
      obsGetJson("/api/v1/observability"),
      obsGetJson("/api/v1/strategies/reference"),
      obsGetJson("/api/v1/research/reference-replay"),
    ]);
    renderObservability(payload);
    renderReferenceLab(catalog, replay);
  } catch (exc) {
    if (error) {
      error.hidden = false;
      error.textContent = `Observability read failed: ${exc instanceof Error ? exc.message : String(exc)}`;
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  const button = obsById("refresh-observability");
  if (button) {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await loadObservability();
      } finally {
        button.disabled = false;
      }
    });
  }

  ["candidate-search", "candidate-state-filter", "candidate-promoted-only"].forEach((id) => {
    const control = obsById(id);
    if (!control) return;
    const eventName = id === "candidate-search" ? "input" : "change";
    control.addEventListener(eventName, renderCandidateRows);
  });

  const closeCandidate = obsById("candidate-dialog-close");
  if (closeCandidate) {
    closeCandidate.addEventListener("click", () => {
      const dialog = obsById("candidate-dialog");
      if (dialog && typeof dialog.close === "function") dialog.close();
    });
  }

  loadObservability();
});
