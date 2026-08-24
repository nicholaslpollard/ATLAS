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
  if (["AVAILABLE", "ACCEPTED", "COMPLETE", "HEALTHY", "PROMOTED", "STACKED_PREP_GREEN", "RECENT", "INPUTS_APPEAR_READY", "SUBSCRIBED", "REALTIME", "FRESH"].includes(normalized)) return "state-ok";
  if (["STACKED_PREP", "WAITING_EXTERNAL", "WARM", "CAUTIOUS", "OLDER", "CONNECTING", "CONNECTED", "AUTHENTICATED"].includes(normalized)) return "state-warn";
  if (["UNAVAILABLE", "BLOCKED", "ERROR", "REJECT", "NOT_READY", "STOPPED", "DEGRADED", "DISCONNECTED", "STALE"].includes(normalized)) return "state-danger";
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
    const payload = await obsGetJson("/api/v1/observability");
    renderObservability(payload);
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
