# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-27 after Phase29 `ACCEPTED_NEGATIVE`.**

This document controls the mission, anti-drift rules, remaining phase sequence, GUI/web/deployment path, and phase acceptance model for ATLAS. Accepted code/evidence on `main` controls historical fact; this roadmap controls future direction.

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. the active phase specification;
4. `docs/phase_flow.md`;
5. `docs/phase_plain_english_contract.md`;
6. accepted code, validators, CI/PR evidence, and older phase documents as provenance.

## 1. Mission and end goal

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

> **Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.**

Profit is never guaranteed. ATLAS is judged by defensible positive expected value after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin—not by trade count, alert count, or attractive backtests.

## 2. Locked architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Persistent roles:

- Parquet = durable analytical/history lake.
- DuckDB = analytical/query engine.
- PostgreSQL = future persistent operational state after later promotion.
- Massive = primary broad-market/reference provider.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = explicit/manual secondary; **no automatic broker failover**.
- ML = probability/predictive evidence, never standalone trade authority.
- alpha/strategy evidence must earn historical analytical support through frozen gates.
- AI = independent audit/challenge layer, not unilateral authority.
- browser/web GUI = operator surface, never a second trading engine.
- deployment packages accepted Python authority rather than reimplementing it.

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
13. Root cause before workaround: no weakened validators, ignored discrepancies, repair-wrapper stacks, post-result threshold changes, or special authority paths to manufacture PASS.
14. Preserve provider-native ticker text/case and exact PIT identity; ticker alone never proves continuity.
15. No fabricated pre-2021 intraday history.
16. Finalized canonical facts outrank provisional state.
17. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
18. Protected performance is finalist-only. Once a holdout outcome is read, that holdout is consumed for later alpha selection.
19. A legitimate negative research phase may be accepted but cannot satisfy a downstream positive-entry condition.
20. When a research family fails, the next research phase must change the economic/information mechanism rather than retune the failed family after observing results.

## 4. Accepted foundation through Phase29

### Phases 1–10

Accepted project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB data, PIT instrument identity/history, live market state, deterministic features, PIT universe eligibility, broad discovery/hysteresis, market/sector/ticker regimes, and conventional ML probability/evaluation.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

### Phases 11–14

Accepted strategy catalog/evaluation and regime routing, promoted-only analogue/scenario research, context/news/options/instrument/geometry/portfolio-risk planning, and independent AI audit/alert artifacts.

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

### Phases 15–23

Accepted broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary architecture, browser/API operational primitives, provider-read readiness, real Webull sandbox submit/cancel evidence, observability, restart-safe orchestration, centralized default-deny PAPER authority, routine Webull-primary PAPER runner, and finalized-session current analytical production binding.

### Phases 24–25

Phase24 tested bounded incumbent strategy variants and found no supported challenger. Phase25 reconstructed the exact historical production candidate/routing path and proved the earlier population mismatch did not hide incumbent edge.

### Phase26 — deterministic/composite self-feature alpha

24 preregistered candidates; 21,483 development observations; zero selection survivors/finalists/support; zero protected returns; independent and anti-workaround PASS. Merged PR #30 at `2074808605cf85b5462e5999ed1836d68b0434c3` as `ACCEPTED_NEGATIVE`.

### Phase27 — cross-sectional expected-return learning/ranking

Eight bounded architecture/direction hypotheses; 18,111 development rows; zero selection survivors/winners/finalists/support; zero protected reads; independent and anti-workaround PASS. Merged PR #31 at `dc015f51232dc66ba94b6175c276a0227d5a3761` as `ACCEPTED_NEGATIVE`.

### Phase28 — cross-stock lead-lag & residual network alpha

Eight frozen relational hypotheses using a 60-pair asymmetric lead-lag network and residual signals. Target evidence: 14,466 development network rows, 741 protected predictors, zero survivors/winners/finalists/support, zero protected candidate/return reads, holdout unconsumed, independent PASS, anti-workaround PASS. PR #32 merged at `285f112d51463dd1e06ea4e874a882ad98f71dc5` as `ACCEPTED_NEGATIVE`.

### Phase29 — relative-value statistical-arbitrage confirmation alpha

Four frozen PCA-residual / nearest-distance-pair LONG/SHORT hypotheses. Target and full closeout evidence:

- development relative-value rows: **14,523**;
- protected relative-value predictor rows: **745**;
- selection survivors/winners/finalists/supported: **0 / 0 / 0 / 0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- end-to-end anti-workaround audit: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0**;
- exact local closeout head: `e078fe56cad4900be54bf39d7d88679d2f6dc4df`;
- disposition: **`ACCEPTED_NEGATIVE`**.

Phase29 therefore grants no historical analytical `SUPPORTED` alpha and does not satisfy the entry condition for signal-to-trade construction.

### Research conclusion after Phase29

ATLAS has now rejected four materially distinct market-data alpha classes under frozen modern standards:

1. deterministic/composite focal self-feature rules;
2. same-stock cross-sectional learned rankings;
3. cross-stock residual/lead-lag predictive relationships;
4. trailing relative-value mean-reversion confirmation via PCA residuals / nearest historical pairs.

Validated alpha remains the blocker. The inherited `2026-05-12` through `2026-08-11` master protected predictor window remains genuinely outcome-unopened because Phases26–29 all read zero protected returns.

The next research phase must use a materially different information source/mechanism. It may not retune Phases26–29.

## 5. Research and execution standards

### Data integrity

- exact PIT identities/safe intervals;
- no current-survivor projection backward;
- ambiguity quarantined rather than guessed;
- deterministic lineage and idempotent/resumable evidence generation;
- split/corporate-action handling;
- provider-native ticker preservation.

### Alpha research

As applicable: chronological development/internal/protected separation, purge/embargo, session/cross-sectional dependence handling, realistic costs, sample/concentration controls, year/regime/liquidity robustness, multiplicity/selection-bias control, simple baselines, and frozen definitions before protected evidence.

Prediction accuracy, IC, win rate, or a positive raw mean is insufficient. `SUPPORTED` requires robust positive after-cost economic evidence under the frozen phase standard.

### Risk/execution

Later trade construction must optimize after-cost risk-adjusted account growth, permit PASS/no-trade, model liquidity/capacity and options-specific risk, enforce deterministic IDs/pre-trade limits, reconcile broker state, prevent duplicate submission, and fail closed on uncertain writes.

## 6. Phase = gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority.

## 7. Next Phase30 — Event-Driven Public-Information Alpha

**Purpose:** test whether point-in-time public company information arrival contains robust after-cost directional confirmation/predictive value that is genuinely distinct from the price/technical/relational mechanisms rejected in Phases26–29.

**Entry condition:** Phase29 accepted negative with zero protected return reads and the master holdout unconsumed. Satisfied by the Phase29 closeout evidence above.

### Why this mechanism is next

Massive exposes ticker-linked financial news with explicit `published_utc` timestamps, article metadata, associated tickers, and sentiment fields through its Stocks News API. That makes a historical public-information mechanism operationally plausible without inventing a new provider architecture. Finance literature also documents economically meaningful differences between identified-news/no-news periods and between fresh/stale information; those findings motivate hypotheses only and do not grant ATLAS support.

Research basis / implementation references:

- Massive Stocks News API: `https://massive.com/docs/rest/stocks/news`;
- Boudoukh, Feldman, Kogan & Richardson, *Which News Moves Stock Prices? A Textual Analysis*;
- Tetlock, *All the News That's Fit to Reprint: Do Investors React to Stale Information?*.

### Required Phase30 internal sequence

Phase30 remains **one numbered project gate**. Its first work is a non-performance-bearing feasibility/provenance step, not a separate project gate:

1. prove historical news coverage, pagination, timestamp semantics, ticker linkage, entitlement, deterministic replay, and PIT-safe acquisition over the intended development/protected windows;
2. persist immutable raw article evidence and provenance before any outcome analysis;
3. reject fields whose historical model/vintage semantics cannot be proven PIT-safe, or derive deterministic local features only from contemporaneously observable article text/metadata;
4. only after feasibility passes, freeze the finite Phase30 hypothesis library, feature transforms, chronology, outcome horizon, costs, multiplicity, dependence treatment, robustness gates, winner/finalist rules, and protected-read boundary;
5. then implement development selection, internal validation, independent blindness audit, finalist-only protected confirmation, independent reconstruction, and full closeout.

No Phase30 target-performance inspection is allowed before the finite research contract is frozen.

### Authority boundary

Phase30 is historical research only. Provider reads may be authorized only for bounded historical-news acquisition/provenance. Broker writes, order writes, PAPER submits, LIVE writes, automatic broker failover, and frontend trading authority remain zero/disabled.

### Positive outcome

At least one fully confirmed Phase30 hypothesis may receive historical analytical `SUPPORTED` authority and satisfy the entry condition for **Phase31** signal-to-trade construction. It creates no PAPER/LIVE authority.

### Negative outcome

Accept it. Do not reinterpret or retune Phases26–30 after results. A further materially distinct alpha source would require another explicitly rebaselined future research phase; signal-to-trade remains blocked.

## 8. Progressive GUI/web/deployment track

The additional event-driven alpha gate shifts downstream product work one phase later:

- **Phase30:** event-driven public-information alpha; no major frontend build.
- **Phase31:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase32:** historical replay/stress dashboard.
- **Phase33:** prospective SHADOW/PAPER operator web beta.
- **Phase34:** outcome/performance/learning/drift dashboards and governance.
- **Phase35:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase36:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase37:** controlled LIVE activation/disable and evidence-based scaling.

## 9. Remaining master roadmap

### Phase30 — Event-Driven Public-Information Alpha

Execute the PIT/news feasibility, freeze the bounded hypotheses before outcome inspection, and test them under the same anti-leakage/after-cost/robustness/protected-evidence standards described above.

### Phase31 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted Phase12/13/14 capabilities rather than rebuilding them. Model liquidity/slippage, volatility/skew/term structure/Greeks, events, assignment/dividend risk, correlation, concentration, buying power, total heat, and drawdown. Stabilize backend/view-model contracts and a read-only operator prototype. No LIVE.

### Phase32 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Replay the frozen supported system as one account-level process. Measure net expectancy, drawdown/tail loss, risk-adjusted return, cost drag, concentration, regime/year behavior, capacity/liquidity, rejected trades, and stress outcomes. Build replay/stress views backed by exact accepted evidence.

### Phase33 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate on genuinely new unseen sessions with SHADOW and Webull-primary PAPER. Freeze prospective evidence requirements first. Validate freshness/timing, signals, instrument selection, risk sizing, order creation, fills/reconciliation, idempotency, latency, costs, failures/restarts, and prospective economics. LIVE remains unavailable.

### Phase34 — Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI

Trace each decision/rejection/trade/order/fill/position/exit/outcome to exact data/model/strategy/risk versions. Measure MAE/MFE, slippage, P&L, calibration, strategy/regime results, instrument-selection quality, drift, and degradation. Learning never silently self-authorizes changes.

### Phase35 — Production Web Application, Operations & Deployment

Consolidate production web application and accepted Python engine. Promote PostgreSQL operational state/autonomous scheduling only with proven parity, recovery safety, idempotency, and auditability. Engineer services, secure config, migrations, health/logging/metrics, backups, startup/restart, update/rollback, and operator documentation.

### Phase36 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE authority yet.** Harden stale-data, provider/broker outage, partial-fill, cancel/replace, API/UI/network/database/restart, duplicate-prevention, buying-power drift, reconciliation, emergency-disable/flatten, and manual-broker-fallback behavior. Freeze the initial LIVE capital/risk envelope.

### Phase37 — Controlled LIVE Activation & Evidence-Based Scaling

Enable LIVE only through explicit authorization with deliberately small initial exposure, hard risk/loss limits, reconciliation/health, kill capability, manual fallback, and no automatic broker failover. Scale only from evidence; later strategy/model/risk changes require new accepted gates.

## 10. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted negative science cannot substitute for it.
