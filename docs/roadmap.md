# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-27 after Phase27 ACCEPTED_NEGATIVE.**

This document controls the long-term mission, anti-drift rules, remaining phase sequence, GUI/web/deployment path, and phase acceptance model for ATLAS. Accepted code/evidence on `main` controls what already exists; this roadmap controls what the project is trying to become and what must happen next.

Future continuation order:

1. this roadmap;
2. `docs/current_status.md`;
3. the active phase specification;
4. `docs/phase_flow.md`;
5. `docs/phase_plain_english_contract.md`;
6. accepted code, validators, CI/PR evidence, and older phase documents as provenance.

When older documents conflict with accepted `main` or this roadmap, accepted `main` controls historical fact and this roadmap controls future direction.

## 1. Mission and end goal

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

> **Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.**

Profit is never guaranteed. ATLAS is judged by defensible positive expected value after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin—not by trade count, alert count, or impressive-looking backtests.

Capital growth is the objective. Capital preservation and controlled risk are constraints required for compounding.

## 2. Locked architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Persistent roles:

- **Parquet** is the durable analytical/history lake.
- **DuckDB** is the analytical/query engine.
- **PostgreSQL** is the target persistent operational state when a later production phase earns promotion.
- **Massive** is the primary broad-market/reference provider.
- **Webull** is primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- **Alpaca** is explicit/manual secondary/fallback; no automatic broker failover.
- **ML** provides probability/predictive evidence and never creates trade authority by argmax alone.
- **Strategies/alpha models** must earn historical analytical support through frozen evidence gates.
- **AI** is an independent audit/challenge layer, not unilateral trade authority.
- **Browser/web GUI** is the intended operator surface and must never duplicate/bypass engine, risk, broker, or LIVE authority.
- **Deployment/runtime** packages the accepted Python engine; it must not create a separate web-only implementation of trading logic.

## 3. Persistent non-negotiables

1. Alpha before unnecessary plumbing once safety/foundation capability exists.
2. Zero candidates/trades is legitimate; thresholds are never weakened to force activity.
3. Point-in-time data, chronology, realistic costs, leakage controls, dependence-aware statistics, multiplicity controls, protected evidence, and reproducibility are mandatory for alpha claims.
4. No silent self-modification of strategy/model/support/risk authority.
5. Research/community ideas are hypotheses, not evidence.
6. Reuse accepted components rather than rebuilding parallel authority paths without measured cause.
7. Every numbered phase starts and ends with a plain-English operator explanation.
8. GUI is a product surface, not a second trading engine.
9. Deployment is engineered and tested, not improvised.
10. Fail closed on ambiguous identity, stale/missing data, uncertain mutation state, invalid geometry, unknown broker/order state, or unreconciled exposure.
11. PAPER does not imply LIVE.
12. No automatic cross-broker failover.
13. Root cause before workaround: do not weaken validators, ignore discrepancies, stack repair wrappers, change research thresholds after results, or introduce special-case authority merely to obtain PASS.
14. Preserve provider-native ticker text/case and exact PIT identity; ticker text alone never proves identity continuity.
15. No fabricated pre-2021 intraday history.
16. Finalized canonical facts outrank provisional live state.
17. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
18. Protected performance may be read only through a frozen finalist-only read plan. Once a holdout outcome is read, that holdout is consumed for later model/strategy selection.

## 4. Accepted foundations through Phase27

### Phases 1–10

Accepted project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB market data, PIT instrument identity/history, live market state, deterministic features, PIT universe eligibility, broad discovery with hysteresis, market/sector/ticker regimes, and conventional ML probability/evaluation.

Accepted historical daily boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

### Phases 11–14

Accepted strategy catalog/evaluation and regime routing, promoted-only analogue/scenario research, context/news/options/instrument/geometry/portfolio-risk planning, and independent AI audit/alert artifacts.

Accepted Phase11 support still remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

### Phases 15–23

Accepted broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary architecture, browser/API operational primitives, provider-read readiness, real Webull sandbox submit/cancel evidence, observability, restart-safe orchestration, centralized default-deny PAPER authority, routine Webull-primary PAPER runner, and finalized-session current analytical production binding.

### Phases 24–25

Phase24 tested 28 bounded strategy variants and found no supported challenger. Phase25 reconstructed the exact historical production candidate/routing path and showed the old population mismatch did not hide incumbent edge.

### Phase26 — deterministic/composite alpha discovery

Phase26 tested 24 preregistered materially different deterministic/composite candidates on production-path-native observations. The valid target result produced 21,483 development observations, zero selection survivors, zero finalists, zero support, zero protected-return reads, independent PASS, and anti-workaround PASS. Phase26 merged through PR #30 at `2074808605cf85b5462e5999ed1836d68b0434c3` as **ACCEPTED_NEGATIVE**.

### Phase27 — cross-sectional expected-return learning/ranking

Phase27 tested eight frozen architecture/direction hypotheses: discovery-priority baseline, Ridge relative-return prediction, histogram-gradient-boosted relative-return prediction, and pairwise logistic ranking, each LONG/SHORT. The valid target result produced 18,111 development model rows and 920 protected predictor rows, but zero selection survivors, zero winners, zero finalists, zero supported candidates, and zero protected-return reads. Independent validation and the end-to-end anti-workaround audit passed.

Final target closeout at branch head `bfc1c9898a6eb67bb6a9050c8d53802a887a940d` returned **PASS / ACCEPTED_NEGATIVE**, with the protected holdout still unconsumed and signal-to-trade entry false. Phase27 merged through PR #31 at `dc015f51232dc66ba94b6175c276a0227d5a3761`. Post-merge workflow `33107544402` passed Ubuntu and Windows.

### Audit conclusion after Phase27

ATLAS remains architecturally on track, but **validated alpha is still the blocking requirement**. The evidence now rejects both (a) the tested hand-thresholded rule/composite families and (b) the tested same-stock self-feature cross-sectional learning/ranking architectures. The next alpha phase must therefore change the **information source**, not merely the model class or threshold.

The inherited `2026-05-12`–`2026-08-11` master protected predictor window remains outcome-unopened because Phases 26 and 27 both read zero protected returns. It may be used by a later separately preregistered phase only while that zero-read state is independently provable.

## 5. Research and execution standards

### Data integrity

- exact PIT identities and safe intervals;
- no current-survivor projection backward;
- ambiguity quarantined rather than guessed;
- resumable/idempotent acquisition and deterministic lineage;
- split/corporate-action handling where required;
- provider-native ticker preservation.

### Alpha research

As applicable, methodology must include chronological development/internal/protected separation, purge/embargo for overlapping outcomes, session/cross-sectional dependence handling, realistic spread/slippage/fees/borrow assumptions, sample and concentration controls, year/regime/liquidity/direction robustness, multiplicity/selection-bias control, simple baselines, and frozen definitions before protected evidence is inspected.

Prediction accuracy, information coefficient, win rate, or a positive mean alone is insufficient. Historical analytical `SUPPORTED` authority requires robust positive after-cost economic evidence under the frozen phase standard.

### Risk/execution

Later trade construction must optimize after-cost risk-adjusted account growth, permit PASS/no-trade, model liquidity/capacity and options-specific risks, preserve deterministic IDs, enforce pre-trade limits, reconcile broker/order/position state, prevent duplicate submission, and fail closed on uncertain writes.

## 6. Phase = gate model

Starting with Phase26, the numbered phase itself is the project gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK PHASE -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research phases may close `ACCEPTED_NEGATIVE` when the frozen scientific question was answered correctly. Negative evidence grants no downstream authority.

## 7. Active Phase28 — Cross-Stock Lead-Lag & Residual Network Alpha

**Purpose:** test a materially different information source: whether recent moves in other production-relevant stocks lead a focal candidate after common movement is removed.

**Entry condition:** Phase27 accepted/merged as valid negative evidence with zero supported strategies and zero protected-return reads. Satisfied by merge `dc015f51232dc66ba94b6175c276a0227d5a3761` and post-merge CI `33107544402`.

Phase28 must use observation-time network relationships only. It may use the exact current WARM/HOT directional candidate set as a peer universe and trailing canonical daily price history within each ticker's safe identity interval. It must not introduce current-only customer/supplier, industry, ownership, or textual-network metadata and project it backward.

The phase tests a finite preregistered set of deterministic relational/residual signals rather than another broad model search. Required design elements include:

- fixed 3-session outcome horizon;
- fixed trailing lead-lag estimation window;
- common-move residualization using only contemporaneously eligible peer-history returns;
- asymmetric peer-to-focal versus focal-to-peer lag correlation;
- fixed leader count/minimum leader evidence;
- split- and identity-safe history;
- fixed peer-momentum and focal-residual baseline signals;
- same complete-case population across all Phase28 candidates;
- fixed top-tail extraction, no post-result threshold tuning;
- LONG and SHORT evaluated independently;
- global multiplicity control across the complete candidate library;
- chronological selection/internal validation with exact purge;
- dependence-aware confidence bounds, realistic costs, concentration/year/regime robustness;
- at most one finalist per direction and no runner-up substitution after internal failure;
- independent blindness audit before any inherited protected outcome read;
- immutable finalist-only protected read plan;
- independent persisted-artifact reconciliation;
- provider/broker/order/PAPER/LIVE/automation activity zero.

**Authority on positive success:** only Phase28 candidates satisfying the full preregistered standard may receive historical analytical `SUPPORTED` authority and satisfy the entry condition for Phase29. No PAPER or LIVE authority is created.

**If no candidate earns support:** accept the negative result. Do not tune network windows, leader counts, signal tails, or candidate definitions after seeing performance. Keep signal-to-trade construction blocked and choose the next alpha research direction from the new failure evidence.

The active frozen specification is `docs/phase28_cross_stock_lead_lag_residual_network_alpha.md`.

## 8. Progressive GUI/web/deployment track

Because Phase28 is another required alpha gate, the downstream product sequence shifts one phase later:

- **Phase28:** alpha critical path; no major frontend build.
- **Phase29:** stabilize validated signal-to-trade/risk outputs into web-facing contracts and build read-only complete-case prototypes.
- **Phase30:** historical replay/stress dashboard.
- **Phase31:** prospective SHADOW/PAPER operator web beta.
- **Phase32:** outcome/performance/learning/drift dashboards and governance.
- **Phase33:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase34:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase35:** controlled LIVE activation/disable and evidence-based scaling through the production control plane.

## 9. Remaining master roadmap

### Phase29 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** at least one strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert validated signal evidence into the best executable account decision using accepted Phase12/13/14 capabilities rather than rebuilding them. Determine PASS versus trade, stock versus option/defined-risk structure, direction, entry, invalidation/stop, target/exit logic, holding horizon/DTE, quantity, and portfolio admission. Model liquidity, expected slippage/cost, IV/realized volatility, skew/term structure, Greeks, earnings/events, assignment/dividend risk, correlation, concentration, buying power, total heat, and drawdown controls. The optimizer must be allowed to choose no trade.

Stabilize backend/API/view-model contracts and build a read-only operator prototype. No LIVE authority.

### Phase30 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Replay the frozen supported system as one account-level process. Measure net expectancy, drawdown/tail loss, risk-adjusted return, turnover/cost drag, concentration, regime/year behavior, capacity/liquidity, rejected trades, and stress outcomes. Options paths must include spread/slippage and expiration/assignment-specific risk. Build replay/stress dashboard views backed by the exact accepted evidence.

### Phase31 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate on genuinely new unseen sessions with SHADOW and Webull-primary PAPER execution. Freeze prospective evidence requirements before results. Validate timing, freshness, signal generation, instrument selection, risk sizing, order creation, fills/reconciliation, idempotency, latency, cost, failures/restarts, and prospective economics. Web beta may expose only already-accepted SHADOW/PAPER actions. LIVE remains unavailable.

### Phase32 — Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI

Trace every decision/rejection/trade/order/fill/position/exit/outcome to exact data/model/strategy/risk versions. Measure MAE/MFE, slippage, P&L, calibration, strategy/regime performance, instrument-selection quality, drift, and degradation. Learning is governed and never silently self-authorizes production changes.

### Phase33 — Production Web Application, Operations & Deployment

Consolidate the production web application and accepted Python engine. Promote PostgreSQL operational state and autonomous scheduling only with proven parity, restart/recovery safety, idempotency, and auditability. Engineer services, secure configuration, persistence/migrations, scheduler, logs/health/metrics, backups/recovery, startup/shutdown/restart, update/rollback, host setup, and operator documentation.

### Phase34 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE authority yet.** Harden the exact deployed stack under stale data, broker/provider outages, partial fills, cancel/replace races, network/API/UI failures, restart/database faults, duplicate prevention, buying-power drift, reconciliation failures, emergency disable/flatten, and manual broker fallback. Define initial LIVE capital/risk envelope before any real-money activation.

### Phase35 — Controlled LIVE Activation & Evidence-Based Scaling

Enable LIVE only through explicit authorization with a deliberately small initial capital/risk envelope, hard per-trade/portfolio/daily-loss limits, real-time reconciliation/health, kill capability, manual fallback, and no automatic broker failover. Scale capital only from evidence; strategy/model/risk changes still require separately accepted future phases.

## 10. Progression rule

The roadmap is **conditional, not schedule-driven**. A phase number does not guarantee advancement. Positive authority requires the phase's frozen entry/acceptance conditions. Negative scientific evidence may be accepted, but it cannot substitute for missing downstream requirements.
