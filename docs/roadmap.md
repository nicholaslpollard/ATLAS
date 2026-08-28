# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-baselined: 2026-08-28 after Phase30 `ACCEPTED_NEGATIVE`.**

This document controls the ATLAS mission, anti-drift rules, remaining phase sequence, GUI/web/deployment path, and phase acceptance model. Accepted code/evidence on `main` controls historical fact; this roadmap controls future direction.

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

`market/reference/regulatory data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Persistent roles:

- Parquet = durable analytical/history lake.
- DuckDB = analytical/query engine.
- PostgreSQL = future persistent operational state after later promotion.
- Massive = primary broad-market/reference/regulatory-data provider where entitled and validated.
- Current Massive subscription constraint = **Stocks Starter**; do not assume Financials & Ratios Expansion, Options Starter, or paid partner datasets are entitled unless separately proven.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = explicit/manual secondary broker and proven historical Benzinga-news source; **no automatic broker failover**.
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
21. Provider plan/entitlement claims are evidence, not assumptions. A documented endpoint can be used only after the actual ATLAS credential path is proven where entitlement uncertainty exists.
22. Regulatory event dates are not automatically decision timestamps. If exact publication/acceptance time is unavailable, use a conservative later decision boundary rather than infer same-session knowledge.

## 4. Accepted foundation through Phase30

### Phases 1–25

Accepted project/config/session foundations, restartable provider ingestion, canonical Parquet/DuckDB data, PIT instrument identity/history, live market state, deterministic features, PIT universe eligibility, broad discovery/hysteresis, market/sector/ticker regimes, conventional ML probability/evaluation, strategy/routing, promoted-only deep research, news/options/instrument/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary operations, browser/API primitives, restart-safe orchestration, centralized PAPER authority, and exact historical production-path reconstruction.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

Phase11 strategy authority remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

### Phase26 — deterministic/composite self-feature alpha

21,483 development observations; zero survivors/finalists/support; zero protected returns; independent and anti-workaround PASS. PR #30 merged as `ACCEPTED_NEGATIVE`.

### Phase27 — cross-sectional expected-return learning/ranking

18,111 development rows; zero survivors/winners/finalists/support; zero protected reads; independent and anti-workaround PASS. PR #31 merged as `ACCEPTED_NEGATIVE`.

### Phase28 — cross-stock lead-lag & residual network alpha

14,466 development rows; 741 protected predictors; zero survivors/winners/finalists/support; zero protected candidate/return reads; independent PASS. PR #32 merged as `ACCEPTED_NEGATIVE`.

### Phase29 — relative-value statistical-arbitrage confirmation alpha

14,523 development rows; 745 protected predictors; zero survivors/winners/finalists/support; zero protected candidate/return reads; independent/anti-workaround PASS. PR #33 merge `87c9450e1b21606b83489f16ff326235ae92eb2b`; `ACCEPTED_NEGATIVE`.

### Phase30 — event-driven public-information/news-arrival alpha

Phase30 changed the information source to timestamped public news. It acquired 775,164 Massive articles and generated 1,012,022 development metadata news-shock predictor rows. The exact development join contained 3,057 rows / 1,736 tickers / 953 sessions. All four frozen hypotheses failed selection; there were zero survivors, winners, finalists, or supported candidates. Independent reconstruction returned `PASS_NEGATIVE_SAMPLE_GATE_PROOF`.

Phase30 target closeout read zero protected candidate rows and zero protected returns; the inherited protected holdout remains unconsumed. PR #34 merged at `bf673ad82886e7172db0d54a33dd9612fa9ea29e` as `ACCEPTED_NEGATIVE`; post-merge workflow `33141442154` passed Ubuntu and Windows.

### Research conclusion after Phase30

ATLAS has now rejected five materially distinct modern alpha classes under frozen standards:

1. deterministic/composite focal self-feature rules;
2. same-stock cross-sectional learned rankings;
3. cross-stock residual/lead-lag predictive relationships;
4. trailing relative-value mean-reversion via PCA residuals / nearest historical pairs;
5. metadata-only public-news arrival shock combined with same-session reaction.

Validated alpha remains the blocker. The master protected outcome window `2026-05-12` through `2026-08-11` is still genuinely outcome-unopened after Phases26–30.

The next phase therefore changes information mechanism again: SEC-reported insider ownership transactions rather than another price/news transform.

## 5. Research and execution standards

### Data integrity

- exact PIT identities/safe intervals;
- no current-survivor projection backward;
- ambiguity quarantined rather than guessed;
- deterministic lineage and idempotent/resumable evidence generation;
- split/corporate-action handling;
- provider-native ticker preservation;
- source accession/filing identifiers retained for regulatory evidence;
- amendments/duplicate records never silently collapsed into original authority.

### Alpha research

As applicable: chronological development/internal/protected separation, purge/embargo, session/cross-sectional dependence handling, realistic costs, sample/concentration controls, year/regime/liquidity robustness, multiplicity/selection-bias control, simple baselines, and frozen definitions before protected evidence.

Prediction accuracy, IC, win rate, or a positive raw mean is insufficient. `SUPPORTED` requires robust positive after-cost economic evidence under the frozen phase standard.

### Risk/execution

Later trade construction must optimize after-cost risk-adjusted account growth, permit PASS/no-trade, model liquidity/capacity and options-specific risk, enforce deterministic IDs/pre-trade limits, reconcile broker state, prevent duplicate submission, and fail closed on uncertain writes.

## 6. Phase = gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority.

## 7. Active Phase31 — SEC Form-4 Insider-Transaction Alpha

**Purpose:** test whether publicly reported corporate-insider ownership changes contain robust after-cost future-return information distinct from the price/relational/news mechanisms rejected in Phases26–30.

**Entry condition:** Phase30 accepted negative with zero protected return reads and the master holdout unconsumed. **Satisfied.**

### Why this mechanism is next

Massive's Form 4 endpoint exposes SEC accession number, issuer/owner CIK, filing date, transaction date/code, acquired/disposed flag, transaction shares/price/value, post-transaction ownership, direct/indirect ownership, officer/director/10% owner roles, Rule 10b5-1 flag, timeliness, security type, and provider-native ticker associations. Current Massive documentation lists the endpoint as included in all Stocks plans and updated daily during early-access beta, so it is compatible with the existing Stocks Starter subscription without assuming the Financials & Ratios Expansion.

Research literature has repeatedly found that insider purchases are generally more informative than sales and can contain information beyond simple contrarian behavior. Those findings motivate a finite Phase31 hypothesis library only; they grant no ATLAS authority.

### Phase31 internal sequence

Phase31 remains one numbered gate:

1. **feasibility/provenance only:** prove actual Starter credential access, historical coverage at ATLAS boundaries, pagination, field completeness, transaction-code population, ticker/CIK identity, deterministic replay, and immutable raw evidence. Read zero market outcomes;
2. decide whether exact SEC acceptance timestamps can be proven from authoritative source metadata before performance. Until then, the conservative PIT rule is that a Form 4 filing can first affect a signal on the **next XNYS session strictly after its `filing_date`**;
3. only after feasibility passes, freeze the finite hypothesis library, event aggregation rules, eligibility, chronology, outcome horizon(s), costs, multiplicity/dependence treatment, robustness gates, winner/finalist rules, and protected-read plan;
4. build predictor-only Form-4 event frames before outcomes;
5. execute development selection and internal validation;
6. perform independent blindness audit;
7. read protected returns only for frozen finalists, if any;
8. independently reconstruct and close the phase.

No Phase31 target-performance inspection is permitted before the scientific contract is frozen.

### Initial source boundary

The lead source is `GET /stocks/filings/vX/form-4` through the accepted read-only `MassiveRESTClient`. Phase31 does **not** assume access to paid fundamentals/ratios, paid Benzinga partner data, an Options subscription, trade/quote endpoints unavailable on Stocks Starter, or any broker account data.

Form 4 is currently an early-access/beta endpoint. Endpoint/schema/plan changes are therefore explicit feasibility failures or revalidation triggers, never silent substitutions.

### Authority boundary

Phase31 is historical research only. Bounded provider reads for feasibility/acquisition are allowed. Provider writes, broker reads/writes, order writes, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover remain zero/disabled.

### Positive outcome

At least one fully confirmed Phase31 candidate may receive historical analytical `SUPPORTED` authority and satisfy the entry condition for **Phase32** signal-to-trade construction. It creates no PAPER/LIVE authority.

### Negative outcome

Accept it. Do not reinterpret or retune Phases26–31 after results. A further materially distinct alpha source requires another roadmap rebaseline; signal-to-trade remains blocked.

## 8. Progressive GUI/web/deployment track

The additional insider-transaction alpha gate shifts downstream product work one phase later:

- **Phase31:** SEC Form-4 insider-transaction alpha; no major frontend build.
- **Phase32:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase33:** historical replay/stress dashboard.
- **Phase34:** prospective SHADOW/PAPER operator web beta.
- **Phase35:** outcome/performance/learning/drift dashboards and governance.
- **Phase36:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase37:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase38:** controlled LIVE activation/disable and evidence-based scaling.

## 9. Remaining master roadmap

### Phase31 — SEC Form-4 Insider-Transaction Alpha

Execute read-only Form-4 feasibility/provenance first, then freeze and evaluate a bounded insider-transaction hypothesis family under the same PIT/after-cost/robustness/protected-evidence standards used for modern alpha research.

### Phase32 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted Phase12/13/14 capabilities. Include the explicit Option Fair-Value Engine and deterministic news-evidence/re-evaluation layer described in `docs/future_news_sentiment_and_option_fair_value.md`. No LIVE.

### Phase33 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Replay the frozen supported system as one account-level process. Measure net expectancy, drawdown/tail loss, risk-adjusted return, cost drag, concentration, regime/year behavior, capacity/liquidity, rejected trades, and stress outcomes. Build replay/stress views backed by exact accepted evidence.

### Phase34 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate on genuinely new unseen sessions with SHADOW and Webull-primary PAPER. Freeze prospective evidence requirements first. Validate freshness/timing, signals, provider selection, news capture, instrument selection, risk sizing, orders/fills/reconciliation, idempotency, latency, costs, failures/restarts, and prospective economics. LIVE remains unavailable.

### Phase35 — Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI

Trace each decision/rejection/trade/order/fill/position/exit/outcome to exact data/model/strategy/risk versions. Measure MAE/MFE, slippage, P&L, calibration, strategy/regime results, instrument-selection quality, news/option-selection quality, drift, and degradation. Learning never silently self-authorizes changes.

### Phase36 — Production Web Application, Operations & Deployment

Consolidate the production web application and accepted Python engine. Promote PostgreSQL operational state/autonomous scheduling only with proven parity, recovery safety, idempotency, and auditability. Engineer services, secure config, migrations, health/logging/metrics, backups, startup/restart, update/rollback, and operator documentation.

### Phase37 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE authority yet.** Harden stale-data, provider/broker outage, partial-fill, cancel/replace, API/UI/network/database/restart, duplicate-prevention, buying-power drift, reconciliation, emergency-disable/flatten, and manual-broker-fallback behavior. Freeze the initial LIVE capital/risk envelope.

### Phase38 — Controlled LIVE Activation & Evidence-Based Scaling

Enable LIVE only through explicit authorization with deliberately small initial exposure, hard risk/loss limits, reconciliation/health, kill capability, manual fallback, and no automatic broker failover. Scale only from evidence; later strategy/model/risk changes require new accepted gates.

## 10. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted negative science cannot substitute for it.
