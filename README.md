# ATLAS

**Autonomous Trading, Learning, and Analysis System**

**Current as of 2026-09-03 (UTC). This README and `docs/roadmap.md` are the only
living project documents. Every continuation chat must read both in full before
making recommendations or changes.**

ATLAS is the greenfield successor to Chart Monitor. Its purpose is to become a
usable quantitative trading platform that can discover and compare opportunities,
run faithful historical replays, construct risk-controlled trades, operate end to
end with PAPER money, record outcomes, show the operator what is happening, and
improve its strategy library without hindsight or silent self-modification.

Profit is an objective, never a guarantee. Activity, alerts, attractive charts, and
profitable backtests are not substitutes for positive expected value after costs,
controlled risk, prospective evidence, and reliable operation.

## Read this first

1. Read this entire README for the current handoff.
2. Read [`docs/roadmap.md`](docs/roadmap.md) for the complete mission, evidence,
   practitioner-strategy catalog, testing design, gates, and ordered work.
3. Inspect code, tests, immutable phase evidence, and Git history only as needed to
   perform the active roadmap package. Those materials support the two living
   documents; they do not compete with them as current plans.
4. If the two living documents conflict, stop and reconcile both in the same change
   before proceeding.

All earlier README/roadmap versions were archived verbatim under
`docs/archive/2026-09-02-pre-product-rebaseline/`. The old `current_status`,
`phase_flow`, and plain-English files are frozen compatibility snapshots, not
living handoffs. Historical incident, closeout, policy, evidence, and research
documents are immutable records and must not be rewritten to make a later result
look like an original pass.

## Direction established by ATLAS Review Chat 3

The prior roadmap let unsuccessful alpha research block product construction. That
dependency is retired.

ATLAS now advances on two parallel tracks:

- **Track A — Product:** finish the end-to-end operating system using clearly
  labeled reference/baseline strategies in historical replay and operational
  PAPER. Product completion does not imply alpha validation or LIVE eligibility.
- **Track B — Strategy & Research Lab:** catalog practitioner setups, implement
  faithful finite strategy specifications, backtest them without parameter fishing,
  learn where each works or fails, and later add higher-prior academic mechanisms
  and advanced alpha research.

The immediate research priority is practitioner strategies built from observable
price, volume, volatility, trend, momentum, gap, opening, and premarket signals.
They are useful reference mechanisms and product test loads. A Reddit post, book,
charting site, or popular indicator is an **idea source**, not proof of edge.
Academic and replication evidence receives a higher prior evidence weight, but all
strategies must earn ATLAS historical and prospective evidence.

ATLAS is a strategy-selection system, not a single-strategy bot. It will eventually
rank eligible opportunities using frozen, walk-forward estimates of probability,
net expectancy, downside, execution cost, confidence, correlation, concentration,
and current conditions. It must not search indicators live until something agrees
with a desired trade.

## Current repository truth

- Accepted numbered foundation: **through Phase32**, merged on `main`.
- Phases26–32 are scientifically valid `ACCEPTED_NEGATIVE` results.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is
  `ACCEPTED_NEGATIVE` as well.
- Later XBRL, beneficial-ownership, FINRA short-interest, diluted-EPS, and Form 13F
  branches are also closed accepted-negative/source-limited results.
- Retained beneficial-ownership source-gate lineage: source-only feasibility
  mechanism `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`; frozen
  feasibility fingerprint
  `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.
  These are historical source-feasibility identifiers, distinct from the later
  frozen scientific mechanism and preserved for accepted-validator compatibility.
- Historical supported modern alpha remains **0**. No existing strategy is
  historically validated, paper validated, live eligible, or live authorized.
- The master protected outcome window `2026-05-12..2026-08-11` remains
  **unconsumed**. Protected return rows read remain **0** for the retained branches.
- LIVE trading and automatic broker failover remain disabled.
- The former operator pause is satisfied and superseded by the explicit Review
  direction encoded here. Product and practitioner-library work may resume; it
  grants no trading authority by itself.
- The unmerged Review research lineage remains preserved: LIT-01 Heston-Sadka
  calendar-seasonality work is source-inconclusive; LIT-02 terminal-repair work is
  deferred/incomplete. Neither grants alpha support or changes `main` authority.
- The former statement `Phase33 signal-to-trade remains blocked` is retained only
  as historical roadmap provenance. Product signal-to-trade work is now unblocked
  for historical replay and operational PAPER baselines. LIVE remains blocked.
- Product/strategy rebaseline: PR #44 merged to `main` as
  `6b972c4d26dfa350580e269d8010038fe526cf4f`, based on the accepted PR #43 Form
  13F closeout.
- A33/B33 phase-start contracts: PR #45 merged as
  `bc105be4958cce808dbbeb306f0ec58f23b13a6d`. Its six pre-outcome seed
  specifications, broader research taxonomy, authority transition rules, and
  shared opportunity-event contract remain preserved.
- A33/B33 foundation implementation is complete and protected by its exact-head
  acceptance workflow. It has not opened ATLAS historical performance, changed
  strategy authority, or submitted any provider, broker, PAPER, or LIVE mutation.
- The first trusted-lake adapter is implemented for the Massive-only post-seam
  DEVELOPMENT interval. It remains source-only in this repository: no historical
  strategy result has been created or inspected here.
- The adapter package was accepted in PR #47 and merged as
  `646db6e6e44ccd2355c7c2263221f35cd01d5da8`; its post-merge Windows and Ubuntu
  full-suite jobs passed.
- The first A34 RESEARCH account-replay vertical slice is implemented: deterministic
  candidate admission, cash/position accounting, simulated orders, outcomes, equity
  curve, read-only API, and visible browser state. No empirical replay exists in this
  checkout.
- The accepted Phase19 operator-path correction is merged in PR #49 as
  `cc0ecc6995ad977ca6eeb5fc00983ba2926317a0`; its post-merge Windows and Ubuntu
  full-suite jobs passed. The current stacked dashboard, not the legacy Phase16
  shell, is the authoritative local GUI entry point.
- The former Phase39 LIVE numbering is retained: **Phase39** remains Controlled
  LIVE Activation and is still protected by all preceding evidence and authority
  gates.

## What exists now

The accepted foundation already includes provider ingestion, PIT identity/history,
Parquet/DuckDB analytical storage, deterministic features, universe/discovery,
market/sector/ticker regime context, ML evidence, strategy routing, instrument and
trade geometry, portfolio risk planning, AI review boundaries, broker-neutral
SHADOW/PAPER primitives, Webull-primary and manual-Alpaca-secondary controls,
restart-safe orchestration, API/browser primitives, and historical production-path
reconstruction.

Important limitations:

- The accepted Phase11 strategy registry still contains eight simplified daily
  rule variants. A33/B33 adds a separate, versioned reference-strategy catalog so
  accepted behavior is not silently changed.
- The accepted PR #45 six-specification seed catalog remains an immutable
  pre-outcome compatibility layer. The nine direction-specific policies resolve
  its declared implementation blockers without rewriting that accepted lineage.
- The first six practitioner families now have nine direction-specific, complete
  research policies covering universe, signal, side, timing, stop, target, exit,
  sizing, costs, and authority.
- A separate daily reference-feature overlay now supplies the exact indicator
  transitions needed by those policies without changing the accepted 33-feature
  core. Intraday, premarket, and opening-session features remain deferred.
- The existing router applies fixed regime compatibility; it does not yet learn
  conditional, walk-forward strategy performance or calibrated probability.
- A provider-free independent-strategy runner, condition-sliced opportunity/outcome
  records, append-only strategy-trials ledger, and read-only catalog API now exist.
  A read-only trusted-lake adapter now supplies its exact input contract. The first
  fixed, non-learned account replay and browser view now exist; learned selection,
  qualifying PAPER, strategy-management controls, and the complete operator product
  remain unfinished.
- PostgreSQL and the root Docker deployment remain historical scaffolds, not an
  accepted operational database or deployment.

Accepted daily historical provider boundary remains Alpaca SIP through
`2021-08-13` and Massive from `2021-08-16`. Multi-provider history is not invalid
merely because it crosses that documented boundary. No pre-2021 intraday history
may be fabricated.

## A33/B33 reference foundation

The **A33/B33 — Practitioner Strategy Laboratory and Product Rebaseline**
foundation implements:

1. a stable, versioned reference catalog alongside the accepted registry;
2. separate indicators, setup signals, complete trade policies, routing, and
   authority;
3. the missing daily features required by the first six reference families;
4. the first finite daily reference library;
5. a reusable, PIT-safe historical runner and opportunity/outcome
   ledger that records fired, rejected, routed, and counterfactual strategies;
6. report structures by time, market/sector/ticker regime, volatility, liquidity,
   and direction without mining sparse condition combinations;
7. a read-only product/control-plane catalog view and append-only trials ledger;
8. proof that these research baselines cannot become PAPER or LIVE
   authority accidentally; and
9. a read-only adapter from accepted Massive canonical daily partitions and
   retained identity/split evidence into the frozen runner input contract.

The first six families contain nine direction-specific policy versions:

1. 50/200 moving-average trend cross;
2. 20/50 EMA pullback continuation;
3. MACD momentum shift;
4. RSI trend-filtered mean reversion;
5. 20-session Donchian high-volume breakout;
6. Bollinger compression breakout.

Gap/opening-range and premarket relative-volume consolidation breakouts follow only
after trusted minute/premarket coverage and exact session semantics pass a
source-only readiness gate. The Reddit “Highest Volume Day” setup belongs in that
later intraday pack as a quantitatively defined, unverified practitioner hypothesis;
its reported statistics are not ATLAS evidence.

No historical performance is opened until each implemented strategy version has a
frozen universe, signal, direction, timing, exit, risk, cost, and evaluation
contract. One canonical version per genuinely different family comes before
variants.

Frozen A33/B33 contracts:

- reference strategy-policy fingerprint:
  `26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3`;
- strategy-authority fingerprint:
  `a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5`;
- daily reference-feature fingerprint:
  `26a2892a4c4bb5597d2e688e78be8cb7da4fc656872a30fe887cf60669476cb8`.
- trusted-lake adapter contract:
  `reference-lake-adapter-v1-massive-development-split-free-identity-exact`.

All nine policies remain `RESEARCH` authority and are permitted only in
`RESEARCH_REPLAY`. The runner accepts caller-supplied split-adjusted daily bars,
rejects the retained master protected window before feature calculation, creates
signals only at finalized closes, and enters no earlier than the next session open.
It retains fired, rejected, selected-independent, and overlap-suppressed
counterfactual opportunities across the `0/5/10/25/50` bps grid. This is not yet an
account portfolio replay and contains no empirical ATLAS result. Master
protected return rows read: **0**; holdout consumed: **false**; broker writes:
**0**; PAPER submits: **0**; LIVE writes: **0**.

The adapter is deliberately narrower than the accepted complete daily history. V1
uses Massive only from `2021-08-16` through at most `2026-05-11`, requires every
requested XNYS partition, resolves exact identity without current active/delisted
filters, rejects internal stream gaps, and excludes an entire identity if any of its
observed tickers has a documented split in scope. Because retained canonical prices
are unadjusted, only these factor-1-equivalent streams may be labeled
`SPLIT_ADJUSTED`; no factor is guessed. This costs coverage but prevents false
signals and returns. Alpaca pre-seam and split-affected streams remain deferred to a
separately validated adjustment-capable V2.

V1 does not attach historical market, sector, or ticker regime labels. The runner
therefore records those three context fields as `UNAVAILABLE`; price/volume
conditions such as volatility, liquidity, and direction remain available. A34 must
join the accepted regime path with an explicit PIT contract before any regime-sliced
result is reported as evidence.

The next safe operation is one DEVELOPMENT-only historical run of all nine frozen
policies on the user's existing trusted lake, followed by A34 portfolio replay and
the browser replay dashboard. This repository checkout contains no market lake, so
no empirical ATLAS result has been fabricated. Protected return rows read: **0**;
performance opened: **false**.

The accepted local command first runs the adapter, binds its source fingerprint,
and registers the frozen trial before calculating any strategy outcome. It can stop
after source validation or continue through the independent-strategy replay:

```powershell
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py --source-only
.\.venv\Scripts\python.exe scripts\run_a33_b33_reference_development.py
```

The full command writes its adapter report, independent opportunity ledger, account
admission decisions, simulated orders, position outcomes, equity curve, summaries,
and append-only trial records under `data/derived/strategy_lab/`; it does not write
to a provider, broker, PAPER account, or LIVE account and cannot promote authority.

## A34 RESEARCH account replay

The first A34 product vertical slice has frozen portfolio-policy fingerprint
`c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`.
It processes each session in this order: opening exits, opening candidate admission,
intraday daily-bar exits, then closing valuation. The fixed baseline begins with
`$100,000`, risks at most `0.25%` of current equity per admitted position, caps one
position at `10%` of equity, gross exposure at `100%`, open positions at `10`, and
active positions from one strategy family at `3`. Same-session candidates are
balanced by current family load and then stable identifiers; realized returns are
never used to rank them.

This is a **RESEARCH account replay**, not qualifying historical validation. V1 is
long-only: short signals and their independent counterfactual results are retained,
but account admission rejects them until short borrow, locate fees, recalls, and
asymmetric execution are modeled. Correlation and sector controls also remain
explicitly unavailable rather than guessed. A conservative `10` bps round-trip cost
is charged as `5` bps on entry and `5` bps on exit. Candidates without a resolved
historical exit are rejected so the V1 account finishes cash-reconciled and flat.

The local control plane exposes the latest result read-only at
`/api/v1/research/reference-replay`. The browser shows all nine frozen policies,
RESEARCH authority, per-strategy account statistics, replay
return/drawdown/costs, recent completed positions, admission decisions, simulated
order events, and a closing-equity/exposure curve. Before displaying an available
run, the read model verifies the recorded SHA-256 binding and schema of every
decision, order, outcome, and equity artifact; drift fails closed as `INVALID`. It
shows `NOT_RUN` honestly until the trusted-lake command produces artifacts. Policy
promotion: **false**; protected return rows read: **0**; provider writes: **0**;
broker writes: **0**; PAPER submits: **0**; LIVE writes: **0**.

The current operator entry point is the stacked Phase19 dashboard, not the older
Phase16 shell. Start it from the repository root with
`python scripts/run_phase19_control_plane.py` (or
`.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py` on Windows), then
open `http://127.0.0.1:8765`. Its A33/A34 Strategy Laboratory panel reads the
catalog and latest replay through the two local GET endpoints; loading or refreshing
the panel does not call a market-data provider or broker.

## Strategy authority and PAPER/LIVE boundary

Every strategy carries two separate labels:

- **Evidence source:** `PRACTITIONER_BASELINE`, `LITERATURE_ANCHORED`, or
  `INTERNAL_CHALLENGER`.
- **Authority:** `RESEARCH` → `CANDIDATE` → `HISTORICALLY_VALIDATED` →
  `PAPER_VALIDATED` → `LIVE_ELIGIBLE`.

Authority controls what a strategy may do. Ranking controls which eligible
opportunity ATLAS prefers. A high score cannot bypass an authority gate.

Two PAPER modes are required:

- **Operational PAPER** exercises the product with baselines. Results are useful
  for debugging and learning, but cannot qualify a strategy for LIVE.
- **Qualifying PAPER** begins only after a version is historically validated and
  the prospective policy is frozen. It is the strongest empirical gate to LIVE,
  but still must pass profitability, sample, risk, drawdown, stability, execution,
  concentration, and operational checks.

`PAPER P&L > 0` alone is never enough. LIVE also requires `LIVE_ELIGIBLE` status,
system-level readiness, explicit operator authorization, small initial exposure,
hard loss limits, reconciliation, a kill control, and no automatic broker failover.

## Non-negotiable safeguards

- Preserve point-in-time identity, provider-native symbols, chronology, corporate
  actions, delistings, and session semantics; fail closed on ambiguity.
- Do not silently weaken transaction-cost, slippage, spread, borrow, capacity,
  liquidity, or market-impact assumptions.
- Use the retained `0/5/10/25/50` bps diagnostic grid where comparable, with
  10 bps primary and 25 bps stress for signal-level daily screening; executable
  replay must replace generic costs with instrument-, side-, liquidity-, volatility-,
  and order-aware costs.
- Signals computed at a bar close enter no earlier than the next executable event.
  Same-bar high/low cannot fill an order created from that bar's close.
- Treat overlapping trades, shared sessions, tickers, sectors, and market moves as
  dependent observations.
- Keep a trials ledger and apply family-level multiple-testing controls. A hundred
  indicator parameterizations are not a hundred independent discoveries.
- Use chronological walk-forward selection, purging/embargo where labels overlap,
  frozen challengers, and untouched qualifying periods.
- Do not reuse the master protected window for practitioner-library selection.
- No production self-modification. A learned selector or strategy revision is a new
  version that must be frozen, replayed, PAPER qualified, and explicitly promoted.
- Zero trades or negative results are valid. Stop a branch when expected information
  gain no longer justifies its infrastructure or source-repair cost.
- Prefer trusted existing market data. Novel difficult sources must beat simpler
  available experiments on expected research value before receiving priority.

## Data repair and V2 policy

When historical data becomes materially questionable:

1. investigate root cause and reconcile local files, transformations, provider
   semantics, and authoritative sources;
2. repair V1 only when the economic meaning remains trustworthy;
3. otherwise freeze and preserve V1 and its results;
4. build a separately versioned V2 with authoritative sources and explicit
   canonical rules;
5. never substitute V2 underneath an observed experiment or describe it as the
   same experiment; and
6. preserve provenance and old results for audit.

Repeated authoritative-source contradictions do not justify purge/refetch loops
whose only purpose is to make evidence disappear.

## How progress is reported

Every accepted package reports both scientific control and functioning product
progress. Examples include:

- strategy specified and implemented;
- historical replay completed;
- candidate generated and routed;
- trade and portfolio constructed;
- operational PAPER order planned or submitted under explicit authority;
- position managed and outcome recorded;
- strategy statistics and calibration updated;
- replay/dashboard/GUI control functioning;
- PIT audit, cost policy, protected reads, trial count, fingerprints, and authority
  state preserved.

Implementation uses the largest safe coherent package. Each package begins and
ends with a short plain-English account of its goal, capability change, result,
remaining risk, authority change, and next work. Root causes are repaired at the
owning layer; validators and scientific rules are never weakened to manufacture a
pass.

## Historical evidence that remains binding

The complete ledger is in the roadmap and immutable closeout documents. Key facts:

- Phase32 is `ACCEPTED_NEGATIVE`; frozen finalist `solvency_distress_short` had
  **46 event rows / 33 signal sessions / 40 unique instruments** versus
  **50 / 20 / 20**; protected stock/SPY returns remained unread.
- Phase32 scientific policy fingerprint:
  `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`;
  protected return rows read = 0; holdout consumed = false.
- Phase31 SEC Form 4 insider-transaction alpha is `ACCEPTED_NEGATIVE`; it produced
  zero survivors, winners, finalists, support, and protected reads.
- XBRL quality/accrual: 200 documents, 170 accrual-ready and 92 profitability-ready
  issuers; zero development passers; protected reads zero.
- XBRL protected return rows read = **0**.
- XBRL retained lineage: Phase32 merge `69f8aa81289934b71f2652482c747391917c15a3`;
  contract `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
  `FEASIBILITY_PASS`; feasibility fingerprint
  `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
  accepted evidence fingerprint
  `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
  PIT audit fingerprint
  `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`.
- Schedule 13D/13G: 3,652 predictors and 2,412 usable development outcomes; zero
  passers; protected reads zero; closeout fingerprint
  `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- FINRA: 19,343 predictors; `rapid_short_cover_crowded_long` had 257 protected rows
  versus 300 required; no outcomes opened; closeout fingerprint
  `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.
- Diluted EPS: three ambiguous contexts and six metadata contradictions reproduced
  by clean authoritative replay; no outcomes opened; closeout fingerprint
  `29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`.
- Form 13F: 10,431 malformed CUSIPs across 374 accessions reproduced exactly in
  original EDGAR XML; no outcomes opened; closeout fingerprint
  `0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`.

These results may inform future work but may not be retuned into positive findings.
The protected holdout remains unconsumed. LIVE and automatic broker failover remain
disabled.

### Retained exact historical validator statements

The following literals are retained as **historical evidence**, not as the current
product dependency. They allow accepted phase validators to continue recognizing
the facts they were written to certify:

- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Phase32 policy fingerprint: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.
- Phase32 frozen source evidence: 46 event rows / 33 signal sessions / 40 unique instruments.
- Phase33 signal-to-trade remains blocked was the superseded roadmap rule; its LIVE-authority conclusion remains binding, while baseline Product construction is now allowed.
- XBRL protected return rows read = **0**; closeout fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- LIVE and automatic broker failover remain disabled.
