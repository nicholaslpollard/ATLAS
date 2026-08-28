# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-28 after Phase31 `ACCEPTED_NEGATIVE`.**

This document controls the ATLAS mission, anti-drift rules, remaining phase sequence, GUI/web/deployment path, and phase acceptance model. Accepted code/evidence on `main` controls historical fact; this roadmap controls future direction.

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. the active phase specification;
4. `docs/phase_flow.md`;
5. `docs/phase_plain_english_contract.md`;
6. accepted code, validators, CI/PR evidence, and historical phase records.

## 1. Mission

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

> **Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.**

Profit is never guaranteed. ATLAS is judged by defensible positive expected value after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin—not by trade count, alert count, or attractive backtests.

## 2. Locked architecture

`market/reference/regulatory data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Persistent roles:

- Parquet = durable analytical/history lake.
- DuckDB = analytical/query engine.
- PostgreSQL = future persistent operational state after later promotion.
- Massive = primary broad-market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive subscription constraint = **Stocks Starter**; do not assume Financials & Ratios Expansion, Options Starter, or paid partner datasets are entitled unless separately proven.
- Official SEC EDGAR may be used read-only for authoritative regulatory submission provenance when a phase explicitly freezes that source boundary.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = explicit/manual secondary broker; **no automatic broker failover**.
- ML = probability/predictive evidence, never standalone trade authority.
- AI = independent audit/challenge layer, not unilateral authority.
- Browser GUI = operator surface, never a second trading engine.

## 3. Persistent non-negotiables

1. Alpha remains the critical path while accepted execution/safety foundations already exist.
2. Zero candidates/trades is legitimate; thresholds are never weakened to force activity.
3. PIT data, chronology, realistic costs, leakage controls, dependence-aware statistics, multiplicity controls, protected evidence, and reproducibility are mandatory for alpha claims.
4. No silent self-modification of strategy/model/support/risk authority.
5. Research/community ideas are hypotheses, not evidence.
6. Reuse accepted components rather than creating parallel authority without measured cause.
7. Every numbered phase starts and ends with a plain-English operator explanation.
8. GUI is a product surface, not business-logic authority.
9. Deployment is engineered/tested, not improvised.
10. Fail closed on ambiguous identity, stale/missing data, uncertain mutation state, invalid geometry, unknown broker/order state, or unreconciled exposure.
11. PAPER does not imply LIVE.
12. No automatic cross-broker failover.
13. Root cause before workaround: no weakened validators, ignored discrepancies, post-result threshold changes, or special authority paths to manufacture PASS.
14. Preserve provider-native ticker text/case and exact PIT identity; ticker alone never proves continuity.
15. No fabricated pre-2021 intraday history.
16. Finalized canonical facts outrank provisional state.
17. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
18. Protected performance is finalist-only. Once a holdout outcome is read, that holdout is consumed for later alpha selection.
19. A legitimate negative research phase may be accepted but cannot satisfy a downstream positive-entry condition.
20. When a research family fails, the next research phase must change the economic/information mechanism rather than retune the failed family after observing results.
21. Provider plan/entitlement claims are evidence, not assumptions.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available, otherwise use a conservative later boundary.

## 4. Accepted foundation through Phase31

### Phases 1–25

Accepted project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB data, PIT instrument identity/history, live market state, deterministic features, PIT universe eligibility, broad discovery/hysteresis, market/sector/ticker regimes, conventional ML probability/evaluation, strategy/routing, promoted-only deep research, news/options/instrument/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary operations, browser/API primitives, restart-safe orchestration, centralized PAPER authority, and exact historical production-path reconstruction.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

Phase11 strategy authority remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

### Phase26 — deterministic/composite self-feature alpha

21,483 development observations; zero survivors/finalists/support; zero protected returns; `ACCEPTED_NEGATIVE`.

### Phase27 — cross-sectional expected-return learning/ranking

18,111 development rows; zero survivors/winners/finalists/support; zero protected reads; `ACCEPTED_NEGATIVE`.

### Phase28 — cross-stock lead-lag & residual network alpha

14,466 development rows; zero survivors/winners/finalists/support; zero protected return reads; `ACCEPTED_NEGATIVE`.

### Phase29 — relative-value statistical-arbitrage alpha

14,523 development rows; zero survivors/winners/finalists/support; zero protected return reads; `ACCEPTED_NEGATIVE`.

### Phase30 — public-news-arrival alpha

775,164 Massive articles generated 1,012,022 development metadata predictor rows; all four frozen hypotheses failed selection; zero protected candidate/return reads; `ACCEPTED_NEGATIVE`.

### Phase31 — SEC Form-4 insider-transaction alpha

Phase31 changed the information source to SEC-reported insider ownership transactions. Full source-quality/acquisition/predictor work passed, then development read 5,400 frozen predictor rows and produced 5,371 usable outcome rows. All four frozen candidates failed mandatory selection gates; there were zero survivors, winners, finalists, or supported candidates. Independent reconstruction returned `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`.

PR #35 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` as `ACCEPTED_NEGATIVE`. Phase31 read **zero protected candidate rows and zero protected returns**; the master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.

ATLAS has therefore rejected six materially distinct modern alpha mechanisms under frozen standards:

1. deterministic/composite focal self-feature rules;
2. same-stock cross-sectional learned rankings;
3. cross-stock residual/lead-lag relationships;
4. trailing relative-value mean reversion;
5. metadata-only public-news arrival shock;
6. structured SEC Form-4 insider transactions.

Validated alpha remains the blocker. Signal-to-trade construction is still forbidden.

## 5. Research and execution standards

Research phases must freeze hypotheses/outcomes/chronology/costs/dependence/multiplicity/robustness/protected-read rules before governed performance is opened. Feasibility may precede hypothesis freeze only when it reads no target outcomes and grants no alpha authority. Ambiguous identity/source rows are quarantined rather than guessed. Negative evidence remains negative; a later phase cannot rename or retune the same failed mechanism.

Later trade construction must optimize after-cost risk-adjusted account growth, permit PASS/no-trade, model liquidity/capacity and options-specific risk, enforce deterministic IDs/pre-trade limits, reconcile broker state, prevent duplicate submission, and fail closed on uncertain writes.

## 6. Phase = gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority.

## 7. Active Phase32 — SEC 8-K Material Corporate-Event Alpha

**Purpose:** test whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from the mechanisms rejected in Phases26–31.

**Entry condition:** Phase31 accepted negative with zero protected return reads and the master holdout unconsumed. **Satisfied.**

### Why this mechanism is materially different

Phase32 is not another Form-4 threshold variant and is not the Phase30 metadata-only news-arrival family. It uses structured issuer-filed material-event disclosures, exact SEC acceptance timestamps, and official 8-K item labels to define event information. The economic mechanism is post-disclosure repricing/drift after specific corporate events.

### Initial source boundary — feasibility only

Phase32 begins with **non-performance source feasibility**:

1. discover original `8-K` filings through the accepted read-only Massive path `GET /stocks/filings/vX/index`;
2. retrieve a deterministic bounded sample of the corresponding official SEC submission headers under `www.sec.gov/Archives/edgar/`;
3. prove accession reconciliation, historical coverage, provider-native ticker linkage, exact `<ACCEPTANCE-DATETIME>`, and `ITEM INFORMATION` population;
4. preserve immutable raw Massive index rows and exact SEC header evidence;
5. read **zero market outcomes** and freeze **no alpha hypothesis** yet.

Feasibility public-availability rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

Even when an 8-K is accepted while the market is open, feasibility does not authorize same-session execution. The later scientific contract may only become stricter, never earlier than this boundary.

The SEC client must identify ATLAS and remain conservatively rate-limited below the SEC public maximum. SEC reads are official read-only source evidence; they create no provider, broker, PAPER, or LIVE mutation authority.

### After feasibility

Only if the source passes will ATLAS freeze a finite item-defined hypothesis family, exact event aggregation/contradiction rules, PIT identity, outcome horizon(s), costs, multiplicity/dependence treatment, robustness gates, winner/finalist rules, and protected-read plan. No development return may be inspected before that freeze.

Candidate item families such as bankruptcy/default, impairment, delisting, financial-statement non-reliance, or dilution are **ideas only at feasibility** and are not frozen hypotheses.

### Authority boundary

Allowed: bounded read-only Massive and official SEC feasibility reads plus immutable local evidence. Forbidden: market outcomes, protected returns, provider writes, broker reads/writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

### Positive outcome

A future fully confirmed Phase32 candidate may earn historical analytical `SUPPORTED` authority and satisfy the entry condition for Phase33 signal-to-trade construction. Phase32 itself creates no PAPER/LIVE authority.

### Negative outcome

Accept it. Do not reinterpret or retune Phases26–32 after results. Another materially distinct information/economic mechanism would require another roadmap rebaseline.

## 8. Progressive GUI/web/deployment track

The additional 8-K alpha gate shifts the product track one phase later:

- **Phase32:** SEC 8-K material corporate-event alpha; no major frontend build.
- **Phase33:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase34:** historical replay/stress dashboard.
- **Phase35:** prospective SHADOW/PAPER operator web beta.
- **Phase36:** outcome/performance/learning/drift dashboards and governance.
- **Phase37:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase38:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase39:** controlled LIVE activation/disable and evidence-based scaling.

Historical numbering migration note only: the pre-Phase32 roadmap used the labels `Active Phase31 — SEC Form-4 Insider-Transaction Alpha`, `Phase32 — Signal-to-Trade Construction`, and `Phase38 — Controlled LIVE Activation`. Those labels are preserved here as provenance only and are no longer the active numbering.

## 9. Remaining master roadmap

### Phase32 — SEC 8-K Material Corporate-Event Alpha

Execute read-only source feasibility first, then—only if accepted—freeze and evaluate a bounded 8-K event hypothesis family under the same PIT/after-cost/robustness/protected-evidence standards used for prior alpha research.

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted Phase12/13/14 capabilities. Include the Option Fair-Value Engine and deterministic news-evidence/re-evaluation layer. No LIVE.

### Phase34 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Replay the frozen supported system as one account-level process and certify net expectancy, drawdown/tail loss, costs, concentration, capacity, regime/year behavior, and stress outcomes.

### Phase35 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate on genuinely new unseen sessions with SHADOW and Webull-primary PAPER. LIVE remains unavailable.

### Phase36 — Outcomes, Learning, Drift Monitoring & Governance + Performance UI

Trace decisions/trades/outcomes to exact data/model/strategy/risk versions and monitor calibration, economics, slippage, drift, and degradation. Learning never silently self-authorizes changes.

### Phase37 — Production Web Application, Operations & Deployment

Consolidate the production web application and accepted Python engine; promote PostgreSQL operational state/autonomous scheduling only with proven parity, recovery safety, idempotency, and auditability.

### Phase38 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE authority yet.** Harden stale-data, provider/broker outage, partial-fill, cancel/replace, API/UI/network/database/restart, duplicate-prevention, buying-power drift, reconciliation, emergency-disable/flatten, and manual-broker-fallback behavior.

### Phase39 — Controlled LIVE Activation & Evidence-Based Scaling

Enable LIVE only through explicit authorization with deliberately small initial exposure, hard risk/loss limits, reconciliation/health, kill capability, manual fallback, and no automatic broker failover. Scale only from evidence.

## 10. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted negative science cannot substitute for it.
