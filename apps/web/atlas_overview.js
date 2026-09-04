"use strict";

function atlasOverviewNumber(value) {
  const cleaned = String(value || "").replace(/[^0-9+\-.]/g, "");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

function atlasOverviewMoney(value) {
  const parsed = atlasOverviewNumber(value);
  if (parsed === null) return "Unavailable";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(parsed);
}

function atlasOverviewCandidates() {
  return Array.from(document.querySelectorAll("#candidates-body tr")).map((row) => {
    const cells = row.children;
    const priority = atlasOverviewNumber(cells[3]?.textContent);
    const pUp = String(cells[6]?.textContent || "—").trim();
    return {
      ticker: String(cells[0]?.textContent || "—").trim(),
      state: String(cells[1]?.textContent || "UNKNOWN").trim().toUpperCase(),
      direction: String(cells[2]?.textContent || "—").trim().toUpperCase(),
      priority,
      market: String(cells[4]?.textContent || "UNAVAILABLE").trim().toUpperCase(),
      tickerRegime: String(cells[5]?.textContent || "UNAVAILABLE").trim().toUpperCase(),
      pUp,
      pDown: String(cells[7]?.textContent || "—").trim(),
      promoted: /PROMOTED/i.test(String(cells[8]?.textContent || "")),
    };
  }).sort((a, b) => {
    if (a.promoted !== b.promoted) return a.promoted ? -1 : 1;
    return (b.priority ?? -Infinity) - (a.priority ?? -Infinity);
  });
}

function atlasOverviewQuotes() {
  return Array.from(document.querySelectorAll("#live-quotes-body tr")).map((row) => {
    const cells = row.children;
    return {
      ticker: String(cells[0]?.textContent || "—").trim(),
      freshness: String(cells[1]?.textContent || "UNKNOWN").trim().toUpperCase(),
      bid: String(cells[2]?.textContent || "—").trim(),
      ask: String(cells[3]?.textContent || "—").trim(),
      session: String(cells[4]?.textContent || "—").trim().toUpperCase(),
      feed: String(cells[5]?.textContent || "—").trim().toUpperCase(),
    };
  });
}

function atlasOverviewPanel(kicker, title, pageId, linkText = "View") {
  const panel = atlasEl("article", "atlas-panel");
  const head = atlasEl("div", "atlas-panel-head");
  const copy = atlasEl("div");
  copy.append(atlasEl("span", "atlas-panel-kicker", kicker), atlasEl("h2", "", title));
  const button = atlasEl("button", "atlas-panel-link", linkText);
  button.type = "button";
  button.dataset.openPage = pageId;
  head.append(copy, button);
  panel.appendChild(head);
  return panel;
}

function atlasBuildOverviewV2() {
  const page = atlasPage("overview");
  if (!page || document.getElementById("atlas-overview-v2")) return;
  const old = document.getElementById("atlas-overview-grid");
  if (old) old.remove();

  const root = atlasEl("div", "atlas-overview-v2");
  root.id = "atlas-overview-v2";

  const primary = atlasEl("section", "atlas-overview-primary");

  const discovery = atlasOverviewPanel("DISCOVERY SUMMARY", "Current candidate state", "market", "Open Market");
  discovery.classList.add("atlas-discovery-panel");
  const states = atlasEl("div", "atlas-discovery-states");
  [
    ["NORMAL", "atlas-ov2-normal", "normal"],
    ["WATCH", "atlas-ov2-watch", "watch"],
    ["WARM", "atlas-ov2-warm", "warm"],
    ["HOT", "atlas-ov2-hot", "hot"],
  ].forEach(([label, id, state]) => {
    const card = atlasEl("div", `atlas-discovery-state ${state}`);
    card.append(atlasEl("span", "atlas-discovery-label", label));
    const value = atlasEl("strong", "atlas-discovery-value", "0");
    value.id = id;
    const detail = atlasEl("span", "atlas-discovery-detail", "0% of materialized");
    detail.id = `${id}-detail`;
    card.append(value, detail);
    states.appendChild(card);
  });
  const discoveryFoot = atlasEl("div", "atlas-discovery-foot");
  discoveryFoot.innerHTML = '<span>Materialized <strong id="atlas-ov2-total">0</strong></span><span>Promoted <strong id="atlas-ov2-promoted">0</strong></span><span>Session <strong id="atlas-ov2-session">—</strong></span>';
  discovery.append(states, discoveryFoot);

  const candidates = atlasOverviewPanel("CANDIDATES", "Highest-priority setups", "market", "View All");
  candidates.classList.add("atlas-hot-candidates-panel");
  const candidateTable = atlasEl("div", "atlas-hot-table");
  candidateTable.innerHTML = '<div class="atlas-hot-head"><span>Ticker</span><span>State</span><span>Priority</span><span>P(up)</span></div><div id="atlas-ov2-candidate-rows" class="atlas-hot-body"></div>';
  candidates.appendChild(candidateTable);

  const featured = atlasOverviewPanel("FEATURED CASE", "Highest-ranked candidate", "market", "Inspect");
  featured.classList.add("atlas-featured-panel");
  featured.innerHTML += `
    <div class="atlas-featured-symbol-row">
      <div>
        <strong id="atlas-ov2-featured-ticker" class="atlas-featured-ticker">—</strong>
        <span id="atlas-ov2-featured-direction" class="atlas-featured-direction">—</span>
      </div>
      <span id="atlas-ov2-featured-state" class="atlas-state-pill">UNAVAILABLE</span>
    </div>
    <div class="atlas-featured-price">
      <span>MARKET</span>
      <strong id="atlas-ov2-featured-price">Unavailable</strong>
      <small id="atlas-ov2-featured-feed">No fresh quote</small>
    </div>
    <div class="atlas-featured-metrics">
      <div><span>P(up)</span><strong id="atlas-ov2-featured-pup">—</strong></div>
      <div><span>P(down)</span><strong id="atlas-ov2-featured-pdown">—</strong></div>
      <div><span>Priority</span><strong id="atlas-ov2-featured-priority">—</strong></div>
      <div><span>Market regime</span><strong id="atlas-ov2-featured-regime">—</strong></div>
    </div>
    <div id="atlas-ov2-featured-promotion" class="atlas-featured-promotion">No candidate selected.</div>`;

  primary.append(discovery, candidates, featured);

  const secondary = atlasEl("section", "atlas-overview-secondary");

  const market = atlasOverviewPanel("MARKET SNAPSHOT", "Focused live quotes", "market", "Market");
  market.classList.add("atlas-market-snapshot-panel");
  market.innerHTML += '<div id="atlas-ov2-quote-grid" class="atlas-quote-grid"></div><div class="atlas-market-foot"><span id="atlas-ov2-feed-state">Feed unavailable</span><span id="atlas-ov2-feed-events">No market events</span></div>';

  const portfolio = atlasOverviewPanel("PORTFOLIO SUMMARY", "PAPER account", "portfolio", "Portfolio");
  portfolio.classList.add("atlas-portfolio-summary-panel");
  portfolio.innerHTML += `
    <div id="atlas-ov2-equity" class="atlas-big-number">Unavailable</div>
    <div id="atlas-ov2-account-detail" class="atlas-muted">Waiting for reconciled account evidence.</div>
    <div class="atlas-portfolio-four">
      <div><span>Positions</span><strong id="atlas-ov2-positions">0</strong></div>
      <div><span>Unrealized</span><strong id="atlas-ov2-unrealized">Unavailable</strong></div>
      <div><span>Realized gross</span><strong id="atlas-ov2-realized">$0.00</strong></div>
      <div><span>Routing</span><strong id="atlas-ov2-routing">—</strong></div>
    </div>`;

  const ai = atlasOverviewPanel("RECENT AI REVIEWS", "Independent audit", "research", "AI Review");
  ai.classList.add("atlas-ai-summary-panel");
  ai.innerHTML += `
    <div class="atlas-review-list atlas-overview-reviews">
      <div><span class="atlas-dot ok"></span><span>Approve</span><strong id="atlas-ov2-ai-approve">0</strong></div>
      <div><span class="atlas-dot warn"></span><span>Cautious</span><strong id="atlas-ov2-ai-cautious">0</strong></div>
      <div><span class="atlas-dot danger"></span><span>Reject</span><strong id="atlas-ov2-ai-reject">0</strong></div>
    </div>
    <div id="atlas-ov2-ai-date" class="atlas-muted">No review evidence.</div>`;

  const operations = atlasOverviewPanel("OPERATIONS / PIPELINE", "Runtime status", "operations", "Operations");
  operations.classList.add("atlas-operations-summary-panel");
  operations.innerHTML += `
    <div class="atlas-ops-list atlas-overview-ops">
      <div><span>System health</span><strong id="atlas-ov2-health">—</strong></div>
      <div><span>Phase 15 authority</span><strong id="atlas-ov2-phase15">—</strong></div>
      <div><span>Artifact recency</span><strong id="atlas-ov2-recency">—</strong></div>
      <div><span>Broker reconciliation</span><strong id="atlas-ov2-reconciliation">—</strong></div>
      <div><span>Provider writes</span><strong id="atlas-ov2-writes">DISABLED</strong></div>
    </div>`;

  secondary.append(market, portfolio, ai, operations);
  root.append(primary, secondary);
  page.appendChild(root);

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-open-page]");
    if (button?.dataset.openPage) atlasShowPage(button.dataset.openPage, true);
  });

  let tape = document.getElementById("atlas-market-tape");
  if (!tape) {
    tape = atlasEl("div", "atlas-market-tape");
    tape.id = "atlas-market-tape";
    tape.innerHTML = '<div class="atlas-tape-label"><span class="atlas-feed-dot"></span><strong>DATA FEEDS</strong></div><div id="atlas-tape-quotes" class="atlas-tape-quotes"></div><div id="atlas-tape-system" class="atlas-tape-system">READ ONLY</div>';
    document.body.appendChild(tape);
  }
}

function atlasOverviewStateClass(value) {
  const state = String(value || "").toUpperCase();
  if (["HEALTHY", "AVAILABLE", "FRESH", "REALTIME", "ACCEPTED", "VERIFIED", "PROMOTED"].some((token) => state.includes(token))) return "ok";
  if (["HOT", "REJECT", "INVALID", "FAILED", "STALE", "UNAVAILABLE"].some((token) => state.includes(token))) return "danger";
  if (["WARM", "WATCH", "CAUTIOUS", "RESEARCH", "DEGRADED", "NOT_RUN"].some((token) => state.includes(token))) return "warn";
  return "info";
}

function atlasOverviewSyncV2() {
  atlasBuildOverviewV2();
  const candidates = atlasOverviewCandidates();
  const quotes = atlasOverviewQuotes();
  const total = candidates.length;
  const counts = { NORMAL: 0, WATCH: 0, WARM: 0, HOT: 0 };
  candidates.forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(counts, item.state)) counts[item.state] += 1;
  });
  [
    ["NORMAL", "atlas-ov2-normal"],
    ["WATCH", "atlas-ov2-watch"],
    ["WARM", "atlas-ov2-warm"],
    ["HOT", "atlas-ov2-hot"],
  ].forEach(([state, id]) => {
    atlasSet(id, String(counts[state]));
    const pct = total > 0 ? Math.round((counts[state] / total) * 100) : 0;
    atlasSet(`${id}-detail`, `${pct}% of materialized`);
  });
  atlasSet("atlas-ov2-total", String(total));
  atlasSet("atlas-ov2-promoted", String(candidates.filter((item) => item.promoted).length));
  atlasSet("atlas-ov2-session", atlasText("candidate-date-summary") || atlasText("candidate-date") || "—");

  const rows = document.getElementById("atlas-ov2-candidate-rows");
  if (rows) rows.replaceChildren();
  candidates.slice(0, 5).forEach((item) => {
    const row = atlasEl("div", "atlas-hot-row");
    const ticker = atlasEl("strong", "", item.ticker);
    const state = atlasEl("span", `atlas-candidate-state ${item.state.toLowerCase()}`, item.state);
    const priority = atlasEl("span", "", item.priority === null ? "—" : item.priority.toFixed(3));
    const pUp = atlasEl("span", "", item.pUp);
    row.append(ticker, state, priority, pUp);
    rows?.appendChild(row);
  });
  if (rows && candidates.length === 0) {
    rows.appendChild(atlasEl("div", "atlas-empty-mini", "No materialized candidates."));
  }

  const featured = candidates[0] || null;
  const quoteMap = new Map(quotes.map((item) => [item.ticker.toUpperCase(), item]));
  const featuredQuote = featured ? quoteMap.get(featured.ticker.toUpperCase()) : null;
  atlasSet("atlas-ov2-featured-ticker", featured?.ticker || "—");
  atlasSet("atlas-ov2-featured-direction", featured?.direction || "—");
  atlasSet("atlas-ov2-featured-state", featured?.state || "UNAVAILABLE", featured ? atlasOverviewStateClass(featured.state) : "danger");
  atlasSet("atlas-ov2-featured-pup", featured?.pUp || "—");
  atlasSet("atlas-ov2-featured-pdown", featured?.pDown || "—");
  atlasSet("atlas-ov2-featured-priority", featured?.priority === null || !featured ? "—" : featured.priority.toFixed(3));
  atlasSet("atlas-ov2-featured-regime", featured?.market || "UNAVAILABLE");
  atlasSet("atlas-ov2-featured-promotion", featured ? (featured.promoted ? "PROMOTED · eligible case evidence present" : "Not promoted in current materialization") : "No candidate selected.");
  atlasSet("atlas-ov2-featured-price", featuredQuote ? `${featuredQuote.bid} / ${featuredQuote.ask}` : "Unavailable");
  atlasSet("atlas-ov2-featured-feed", featuredQuote ? `${featuredQuote.freshness} · ${featuredQuote.feed} · ${featuredQuote.session}` : "No focused quote for this ticker");

  const quoteGrid = document.getElementById("atlas-ov2-quote-grid");
  if (quoteGrid) quoteGrid.replaceChildren();
  quotes.slice(0, 4).forEach((item) => {
    const card = atlasEl("div", "atlas-quote-card");
    card.innerHTML = `<div><strong>${item.ticker}</strong><span class="${item.freshness === "FRESH" ? "ok" : "warn"}">${item.freshness}</span></div><div class="atlas-quote-prices"><span>Bid <strong>${item.bid}</strong></span><span>Ask <strong>${item.ask}</strong></span></div><small>${item.feed} · ${item.session}</small>`;
    quoteGrid?.appendChild(card);
  });
  if (quoteGrid && quotes.length === 0) quoteGrid.appendChild(atlasEl("div", "atlas-empty-mini", "No focused quotes in persisted market state."));
  atlasSet("atlas-ov2-feed-state", atlasText("live-feed") || "Feed unavailable");
  atlasSet("atlas-ov2-feed-events", atlasText("live-events") || "No market events");

  atlasSet("atlas-ov2-equity", atlasText("paper-account") || "Unavailable");
  atlasSet("atlas-ov2-account-detail", atlasText("paper-account-detail") || "Waiting for reconciled account evidence.");
  const positionRows = Array.from(document.querySelectorAll("#paper-positions-body tr"));
  atlasSet("atlas-ov2-positions", String(positionRows.length));
  let unrealized = 0;
  let unrealizedKnown = false;
  positionRows.forEach((row) => {
    const text = String(row.children[5]?.textContent || "");
    const match = text.match(/[-+]?\$[\d,]+(?:\.\d+)?/);
    if (match) {
      const value = atlasOverviewNumber(match[0]);
      if (value !== null) {
        unrealized += value;
        unrealizedKnown = true;
      }
    }
  });
  atlasSet("atlas-ov2-unrealized", unrealizedKnown ? atlasOverviewMoney(unrealized) : "Unavailable");
  atlasSet("atlas-ov2-realized", atlasText("paper-realized") || "$0.00");
  atlasSet("atlas-ov2-routing", atlasText("paper-routing") || atlasText("selected-routing") || "—");

  atlasSet("atlas-ov2-ai-approve", atlasText("ai-approve") || "0");
  atlasSet("atlas-ov2-ai-cautious", atlasText("ai-cautious") || "0");
  atlasSet("atlas-ov2-ai-reject", atlasText("ai-reject") || "0");
  atlasSet("atlas-ov2-ai-date", atlasText("ai-date") ? `Review session ${atlasText("ai-date")}` : "No review evidence.");

  atlasSet("atlas-ov2-health", atlasText("system-health") || "—");
  atlasSet("atlas-ov2-phase15", atlasText("phase15-state") || "—");
  atlasSet("atlas-ov2-recency", atlasText("artifact-recency") || "—");
  const brokers = Array.from(document.querySelectorAll("#brokers .card"));
  const selectedBroker = atlasText("atlas-top-broker");
  let reconciliation = "UNPOLLED";
  brokers.forEach((card) => {
    if (!selectedBroker || selectedBroker === "UNSELECTED") return;
    if (String(card.textContent || "").toUpperCase().includes(selectedBroker.toUpperCase()) && /Reconciled\s*Yes/i.test(String(card.textContent || ""))) reconciliation = "SYNCED";
  });
  atlasSet("atlas-ov2-reconciliation", reconciliation);
  atlasSet("atlas-ov2-writes", "DISABLED");

  const tapeQuotes = document.getElementById("atlas-tape-quotes");
  if (tapeQuotes) tapeQuotes.replaceChildren();
  quotes.slice(0, 6).forEach((item) => {
    const quote = atlasEl("span", "atlas-tape-quote");
    quote.innerHTML = `<strong>${item.ticker}</strong><span>${item.bid}</span><small>${item.freshness}</small>`;
    tapeQuotes?.appendChild(quote);
  });
  if (tapeQuotes && quotes.length === 0) tapeQuotes.appendChild(atlasEl("span", "atlas-tape-empty", "No focused market quotes"));
  atlasSet("atlas-tape-system", `${atlasText("atlas-top-broker") || "UNSELECTED"} · ${atlasText("atlas-top-mode") || "RESEARCH"} · ${atlasText("live-feed") || "FEED UNAVAILABLE"}`);
}

window.addEventListener("atlas:observability-refreshed", () => {
  window.setTimeout(atlasOverviewSyncV2, 120);
});

window.addEventListener("DOMContentLoaded", () => {
  window.setTimeout(atlasOverviewSyncV2, 90);
  window.setTimeout(atlasOverviewSyncV2, 500);
  window.setInterval(() => {
    if (!document.hidden) atlasOverviewSyncV2();
  }, 1500);
});
