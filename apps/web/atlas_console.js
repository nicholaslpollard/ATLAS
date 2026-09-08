"use strict";

const atlasConsole = {
  pages: [
    ["overview", "Overview", "System summary"],
    ["market", "Market", "Discovery, candidates & regimes"],
    ["research", "Research", "Strategies, ML & AI review"],
    ["portfolio", "Portfolio", "Account, positions & P&L"],
    ["execution", "Execution", "Decisions, orders & outcomes"],
    ["brokers", "Brokers & Data", "Routing, reconciliation & feeds"],
    ["operations", "Operations", "Pipeline, health & lineage"],
    ["controls", "Controls", "Operator policy & safety"],
  ],
  timer: null,
};

function atlasEl(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function atlasIcon(name) {
  const paths = {
    overview: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    market: '<circle cx="12" cy="12" r="9"/><path d="M3.5 12h17M12 3c3 3.2 4.2 6.2 4.2 9S15 17.8 12 21M12 3C9 6.2 7.8 9.2 7.8 12S9 17.8 12 21"/>',
    research: '<path d="M5 19h14M7 16l3-4 3 2 4-7M16 7h3v3"/><circle cx="6" cy="6" r="2"/>',
    portfolio: '<path d="M4 19V8l8-4 8 4v11M3 19h18M8 19v-6h8v6"/>',
    execution: '<path d="M5 5h14M5 12h14M5 19h14"/><circle cx="8" cy="5" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="10" cy="19" r="1.7"/>',
    brokers: '<path d="M3 9l9-5 9 5-9 5-9-5zM5 12v5l7 3 7-3v-5"/>',
    operations: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>',
    controls: '<path d="M4 7h16M4 17h16M8 4v6M16 14v6"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',
  };
  const wrap = atlasEl("span", "atlas-nav-icon");
  wrap.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.overview}</svg>`;
  return wrap;
}

function atlasLogo() {
  const wrap = atlasEl("div", "atlas-brand-mark");
  wrap.innerHTML = '<svg viewBox="0 0 72 72" role="img" aria-label="ATLAS"><defs><filter id="atlasGlow"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><path d="M36 7L8 59h15l13-24 13 24h15L36 7z" fill="none" stroke="currentColor" stroke-width="4" filter="url(#atlasGlow)"/><path d="M22 51h28M36 7v28" fill="none" stroke="currentColor" stroke-width="2" opacity=".85"/></svg>';
  return wrap;
}

function atlasBuildShell() {
  if (document.getElementById("atlas-sidebar")) return;
  document.body.classList.add("atlas-console-active");

  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "/assets/atlas_console.css";
  document.head.appendChild(style);

  const sidebar = atlasEl("aside", "atlas-sidebar");
  sidebar.id = "atlas-sidebar";
  const brand = atlasEl("div", "atlas-brand");
  brand.append(atlasLogo(), atlasEl("div", "atlas-brand-name", "ATLAS"));
  sidebar.appendChild(brand);

  const nav = atlasEl("nav", "atlas-side-nav");
  nav.setAttribute("aria-label", "ATLAS pages");
  atlasConsole.pages.forEach(([id, label]) => {
    const button = atlasEl("button", "atlas-nav-item");
    button.type = "button";
    button.dataset.page = id;
    button.append(atlasIcon(id), atlasEl("span", "atlas-nav-label", label));
    button.addEventListener("click", () => atlasShowPage(id, true));
    nav.appendChild(button);
  });
  sidebar.appendChild(nav);

  const sidebarFoot = atlasEl("div", "atlas-sidebar-foot");
  sidebarFoot.innerHTML = '<span class="atlas-feed-dot"></span><span>ATLAS CONSOLE</span>';
  sidebar.appendChild(sidebarFoot);
  document.body.insertAdjacentElement("afterbegin", sidebar);

  const command = atlasEl("header", "atlas-command-bar");
  command.id = "atlas-command-bar";
  [
    ["Market regime", "atlas-top-regime", "—"],
    ["System health", "atlas-top-health", "—"],
    ["Active broker", "atlas-top-broker", "—"],
    ["Mode", "atlas-top-mode", "—"],
  ].forEach(([label, id, initial]) => {
    const cell = atlasEl("div", "atlas-command-cell");
    cell.append(atlasEl("div", "atlas-command-label", label));
    const value = atlasEl("div", "atlas-command-value", initial);
    value.id = id;
    cell.appendChild(value);
    command.appendChild(cell);
  });
  const clock = atlasEl("div", "atlas-command-clock");
  const time = atlasEl("div", "atlas-clock-time", "—");
  time.id = "atlas-top-time";
  const session = atlasEl("div", "atlas-clock-session", "LOCAL CONSOLE");
  clock.append(time, session);
  command.appendChild(clock);
  document.body.appendChild(command);

  const main = document.querySelector("main");
  if (!main) return;
  main.classList.add("atlas-console-main");
  const pageHost = atlasEl("div", "atlas-page-host");
  pageHost.id = "atlas-page-host";
  main.insertAdjacentElement("afterbegin", pageHost);

  atlasConsole.pages.forEach(([id, title, subtitle]) => {
    const page = atlasEl("section", "atlas-page");
    page.id = `atlas-page-${id}`;
    page.dataset.page = id;
    const head = atlasEl("div", "atlas-page-heading");
    const titleWrap = atlasEl("div");
    titleWrap.append(atlasEl("div", "atlas-page-kicker", "ATLAS"), atlasEl("h1", "atlas-page-title", title));
    head.append(titleWrap, atlasEl("p", "atlas-page-subtitle", subtitle));
    page.appendChild(head);
    pageHost.appendChild(page);
  });

  atlasBuildOverview();
  atlasBuildControls();
  atlasRouteSections();
  const requested = String(location.hash || "").replace(/^#\/?/, "");
  atlasShowPage(atlasConsole.pages.some(([id]) => id === requested) ? requested : "overview", false);
}

function atlasPage(id) {
  return document.getElementById(`atlas-page-${id}`);
}

function atlasShowPage(id, updateHash) {
  atlasConsole.pages.forEach(([pageId]) => {
    const page = atlasPage(pageId);
    if (page) page.classList.toggle("active", pageId === id);
    const button = document.querySelector(`.atlas-nav-item[data-page="${pageId}"]`);
    if (button) button.classList.toggle("active", pageId === id);
  });
  if (updateHash) history.replaceState(null, "", `#${id}`);
  window.scrollTo({ top: 0, behavior: "auto" });
}

function atlasTopMainChild(node) {
  const main = document.querySelector("main");
  let current = node;
  while (current && current.parentElement && current.parentElement !== main && current.parentElement.id !== "atlas-page-host") {
    current = current.parentElement;
  }
  return current;
}

function atlasMoveAnchor(anchorId, pageId, includeHeader = false) {
  const anchor = document.getElementById(anchorId);
  const page = atlasPage(pageId);
  if (!anchor || !page) return;
  const top = atlasTopMainChild(anchor);
  if (!top || top.classList.contains("atlas-page")) return;
  if (includeHeader) {
    const previous = top.previousElementSibling;
    if (previous && previous.classList.contains("section-head")) page.appendChild(previous);
  }
  page.appendChild(top);
}

function atlasMovePaperChild(anchorId, pageId) {
  const root = document.getElementById("paper-dashboard");
  const page = atlasPage(pageId);
  const anchor = document.getElementById(anchorId);
  if (!root || !page || !anchor) return;
  let node = anchor;
  while (node.parentElement && node.parentElement !== root) node = node.parentElement;
  if (node.parentElement === root) page.appendChild(node);
}

function atlasRouteSections() {
  const main = document.querySelector("main");
  if (!main) return;
  const sourceSummary = main.querySelector(":scope > .summary-grid");
  if (sourceSummary) sourceSummary.classList.add("atlas-source-only");

  atlasMoveAnchor("pipeline-stages", "operations", true);
  atlasMoveAnchor("phase19-readiness-controls", "brokers", false);

  atlasMoveAnchor("reference-lab-banner", "research", true);
  atlasMoveAnchor("reference-lab-strategies", "research", false);
  atlasMoveAnchor("reference-lab-strategy-body", "research", false);
  atlasMoveAnchor("reference-lab-equity-chart", "research", false);
  atlasMoveAnchor("reference-lab-decisions-body", "research", false);

  atlasMoveAnchor("candidate-date-summary", "market", true);
  atlasMoveAnchor("candidate-search", "market", false);
  atlasMoveAnchor("ai-date", "research", true);

  atlasMoveAnchor("outcome-count", "execution", true);
  atlasMoveAnchor("outcomes-table", "execution", false);
  atlasMoveAnchor("brokers", "brokers", true);
  atlasMoveAnchor("actions-table", "operations", true);
  atlasMoveAnchor("lineage-merge", "operations", true);

  atlasMoveAnchor("live-market-panel", "market", true);
  atlasMoveAnchor("live-quotes-table", "market", false);

  const paperRoot = document.getElementById("paper-dashboard");
  if (paperRoot) {
    const paperHead = paperRoot.querySelector(":scope > .section-head");
    const paperBanner = document.getElementById("paper-dashboard-banner");
    if (paperHead) atlasPage("portfolio")?.appendChild(paperHead);
    if (paperBanner) atlasPage("portfolio")?.appendChild(paperBanner);
    atlasMovePaperChild("paper-state", "portfolio");
    atlasMovePaperChild("paper-positions-table", "portfolio");
    atlasMovePaperChild("paper-health-list", "portfolio");
    atlasMovePaperChild("paper-decisions-table", "execution");
    atlasMovePaperChild("paper-closed-table", "execution");
    if (!paperRoot.children.length) paperRoot.remove();
  }
}

function atlasBuildOverview() {
  const page = atlasPage("overview");
  if (!page || document.getElementById("atlas-overview-grid")) return;
  const grid = atlasEl("div", "atlas-overview-grid");
  grid.id = "atlas-overview-grid";

  const market = atlasEl("article", "atlas-panel atlas-overview-market");
  market.innerHTML = '<div class="atlas-panel-head"><div><span class="atlas-panel-kicker">MARKET INTELLIGENCE</span><h2>Candidate surface</h2></div><button class="atlas-panel-link" data-open-page="market">Open Market</button></div><div class="atlas-stat-strip"><div><span>Visible</span><strong id="atlas-ov-candidates">0</strong></div><div><span>Hot</span><strong id="atlas-ov-hot" class="hot">0</strong></div><div><span>Warm</span><strong id="atlas-ov-warm" class="warm">0</strong></div><div><span>Promoted</span><strong id="atlas-ov-promoted">0</strong></div></div><div class="atlas-mini-table"><div class="atlas-mini-head"><span>Ticker</span><span>State</span><span>P(up)</span></div><div id="atlas-ov-candidate-rows" class="atlas-mini-body"></div></div>';

  const portfolio = atlasEl("article", "atlas-panel");
  portfolio.innerHTML = '<div class="atlas-panel-head"><div><span class="atlas-panel-kicker">PORTFOLIO</span><h2>Paper account</h2></div><button class="atlas-panel-link" data-open-page="portfolio">View</button></div><div id="atlas-ov-equity" class="atlas-big-number">Unavailable</div><div id="atlas-ov-account-detail" class="atlas-muted">Waiting for reconciled account evidence.</div><div class="atlas-two-stat"><div><span>Open positions</span><strong id="atlas-ov-positions">0</strong></div><div><span>Gross P&L</span><strong id="atlas-ov-pnl">$0.00</strong></div></div>';

  const ai = atlasEl("article", "atlas-panel");
  ai.innerHTML = '<div class="atlas-panel-head"><div><span class="atlas-panel-kicker">AI REVIEW</span><h2>Independent audit</h2></div><button class="atlas-panel-link" data-open-page="research">Research</button></div><div class="atlas-review-list"><div><span class="atlas-dot ok"></span><span>Approve</span><strong id="atlas-ov-ai-approve">0</strong></div><div><span class="atlas-dot warn"></span><span>Cautious</span><strong id="atlas-ov-ai-cautious">0</strong></div><div><span class="atlas-dot danger"></span><span>Reject</span><strong id="atlas-ov-ai-reject">0</strong></div></div><div id="atlas-ov-ai-date" class="atlas-muted">No review evidence.</div>';

  const operations = atlasEl("article", "atlas-panel");
  operations.innerHTML = '<div class="atlas-panel-head"><div><span class="atlas-panel-kicker">OPERATIONS</span><h2>Pipeline status</h2></div><button class="atlas-panel-link" data-open-page="operations">Details</button></div><div class="atlas-ops-list"><div><span>System health</span><strong id="atlas-ov-health">—</strong></div><div><span>Phase 15</span><strong id="atlas-ov-phase15">—</strong></div><div><span>Artifacts</span><strong id="atlas-ov-recency">—</strong></div><div><span>Action ledger</span><strong id="atlas-ov-ledger">—</strong></div></div>';

  const feed = atlasEl("article", "atlas-panel atlas-overview-feed");
  feed.innerHTML = '<div class="atlas-panel-head"><div><span class="atlas-panel-kicker">DATA FEED</span><h2>Market input</h2></div><button class="atlas-panel-link" data-open-page="brokers">Feeds</button></div><div class="atlas-feed-state"><strong id="atlas-ov-feed">UNAVAILABLE</strong><span id="atlas-ov-session">Session unavailable</span></div><div id="atlas-ov-feed-detail" class="atlas-muted">No persisted live-market state.</div>';

  grid.append(market, portfolio, ai, operations, feed);
  page.appendChild(grid);
  page.addEventListener("click", (event) => {
    const button = event.target.closest("[data-open-page]");
    if (button) atlasShowPage(button.dataset.openPage, true);
  });
}

function atlasBuildControls() {
  const page = atlasPage("controls");
  if (!page || document.getElementById("atlas-control-matrix")) return;
  const note = atlasEl("div", "atlas-control-banner");
  note.innerHTML = '<strong>Policy display</strong><span>Only controls backed by accepted authority become editable. Unavailable controls remain visibly locked rather than simulated.</span>';
  page.appendChild(note);

  const matrix = atlasEl("div", "atlas-control-matrix");
  matrix.id = "atlas-control-matrix";
  const items = [
    ["Mode", "atlas-ctl-mode", "Current runtime authority"],
    ["Execution broker", "atlas-ctl-broker", "Operator-selected PAPER routing"],
    ["Market data", "atlas-ctl-feed", "Independent from execution broker"],
    ["Automatic failover", "atlas-ctl-failover", "Locked off by policy"],
    ["LIVE authority", "atlas-ctl-live", "Not promoted"],
    ["Browser mutation", "atlas-ctl-browser", "Read-only observability path"],
    ["Local refresh", "atlas-ctl-refresh", "Browser-local artifact polling"],
    ["Strategy authority", "atlas-ctl-strategy", "Research until separately promoted"],
  ];
  items.forEach(([label, id, detail]) => {
    const card = atlasEl("article", "atlas-control-card");
    card.append(atlasEl("div", "atlas-control-label", label));
    const value = atlasEl("div", "atlas-control-value", "—");
    value.id = id;
    card.append(value, atlasEl("div", "atlas-control-detail", detail));
    const lock = atlasEl("div", "atlas-control-lock", "POLICY-BOUND");
    card.appendChild(lock);
    matrix.appendChild(card);
  });
  page.appendChild(matrix);
}

function atlasText(id) {
  const node = document.getElementById(id);
  return node ? String(node.textContent || "").trim() : "";
}

function atlasSet(id, value, state = "") {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = value || "—";
  if (state) node.dataset.state = state;
}

function atlasSyncConsole() {
  atlasRouteSections();

  const health = atlasText("system-health") || "UNKNOWN";
  const routing = atlasText("selected-routing") || "Not selected";
  const routeParts = routing.split("/").map((item) => item.trim()).filter(Boolean);
  const broker = routeParts[0] && routeParts[0] !== "Not selected" ? routeParts[0].toUpperCase() : "UNSELECTED";
  const mode = routeParts[1] ? routeParts[1].toUpperCase() : (atlasText("paper-routing").includes("PAPER") ? "PAPER" : "RESEARCH");
  const candidateRows = Array.from(document.querySelectorAll("#candidates-body tr"));
  const marketRegime = candidateRows.length > 0 && candidateRows[0].children[4]
    ? candidateRows[0].children[4].textContent.trim().toUpperCase()
    : "UNAVAILABLE";

  atlasSet("atlas-top-regime", marketRegime, marketRegime.includes("BULL") ? "ok" : marketRegime.includes("BEAR") ? "danger" : "warn");
  atlasSet("atlas-top-health", health.toUpperCase(), health.toUpperCase() === "HEALTHY" ? "ok" : "warn");
  atlasSet("atlas-top-broker", broker, broker === "UNSELECTED" ? "warn" : "info");
  atlasSet("atlas-top-mode", mode, mode === "PAPER" ? "info" : "warn");
  atlasSet("atlas-top-time", new Date().toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit" }));

  let hot = 0;
  let warm = 0;
  const mini = document.getElementById("atlas-ov-candidate-rows");
  if (mini) mini.replaceChildren();
  candidateRows.slice(0, 5).forEach((row) => {
    const cells = row.children;
    const state = cells[1]?.textContent.trim().toUpperCase() || "—";
    if (state === "HOT") hot += 1;
    if (state === "WARM") warm += 1;
    if (mini) {
      const line = atlasEl("div", "atlas-mini-row");
      line.append(
        atlasEl("strong", "", cells[0]?.textContent.trim() || "—"),
        atlasEl("span", state === "HOT" ? "hot" : state === "WARM" ? "warm" : "", state),
        atlasEl("span", "", cells[6]?.textContent.trim() || "—")
      );
      mini.appendChild(line);
    }
  });
  candidateRows.slice(5).forEach((row) => {
    const state = row.children[1]?.textContent.trim().toUpperCase();
    if (state === "HOT") hot += 1;
    if (state === "WARM") warm += 1;
  });
  atlasSet("atlas-ov-candidates", String(candidateRows.length));
  atlasSet("atlas-ov-hot", String(hot));
  atlasSet("atlas-ov-warm", String(warm));
  atlasSet("atlas-ov-promoted", atlasText("candidate-promoted-summary") || "0");

  atlasSet("atlas-ov-equity", atlasText("paper-account") || "Unavailable");
  atlasSet("atlas-ov-account-detail", atlasText("paper-account-detail") || "Waiting for reconciled account evidence.");
  atlasSet("atlas-ov-positions", String(document.querySelectorAll("#paper-positions-body tr").length));
  atlasSet("atlas-ov-pnl", atlasText("paper-realized") || "$0.00");

  atlasSet("atlas-ov-ai-approve", atlasText("ai-approve") || "0");
  atlasSet("atlas-ov-ai-cautious", atlasText("ai-cautious") || "0");
  atlasSet("atlas-ov-ai-reject", atlasText("ai-reject") || "0");
  atlasSet("atlas-ov-ai-date", atlasText("ai-date") ? `Review session ${atlasText("ai-date")}` : "No review evidence.");

  atlasSet("atlas-ov-health", health || "—");
  atlasSet("atlas-ov-phase15", atlasText("phase15-state") || "—");
  atlasSet("atlas-ov-recency", atlasText("artifact-recency") || "—");
  atlasSet("atlas-ov-ledger", atlasText("ledger-state") || "—");

  atlasSet("atlas-ov-feed", atlasText("live-feed") || "UNAVAILABLE");
  atlasSet("atlas-ov-session", atlasText("live-session") || "Session unavailable");
  atlasSet("atlas-ov-feed-detail", atlasText("live-events") || "No persisted live-market state.");

  atlasSet("atlas-ctl-mode", mode);
  atlasSet("atlas-ctl-broker", broker);
  atlasSet("atlas-ctl-feed", atlasText("live-feed") || "UNAVAILABLE");
  atlasSet("atlas-ctl-failover", "DISABLED");
  atlasSet("atlas-ctl-live", "DISABLED");
  atlasSet("atlas-ctl-browser", "READ ONLY");
  atlasSet("atlas-ctl-refresh", atlasText("local-observability-interval") ? `${atlasText("local-observability-interval")}s` : "LOCAL ONLY");
  atlasSet("atlas-ctl-strategy", "RESEARCH");
}

window.addEventListener("hashchange", () => {
  const requested = String(location.hash || "").replace(/^#\/?/, "");
  if (atlasConsole.pages.some(([id]) => id === requested)) atlasShowPage(requested, false);
});

window.addEventListener("atlas:observability-refreshed", () => {
  window.setTimeout(atlasSyncConsole, 50);
});

window.addEventListener("DOMContentLoaded", () => {
  atlasBuildShell();
  window.setTimeout(atlasSyncConsole, 50);
  window.setTimeout(atlasSyncConsole, 400);
  atlasConsole.timer = window.setInterval(() => {
    if (!document.hidden) atlasSyncConsole();
  }, 1000);
});
