# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-30 (America/New_York). Phase32 and the later SEC XBRL research family are closed `ACCEPTED_NEGATIVE`. The current pre-Phase33 SEC Schedule 13D/13G beneficial-ownership mechanism has passed repaired source feasibility, frozen its finite scientific contract, and is paused at a preserved pre-outcome development acquisition transport failure after 3500/5200 source-only predictor items. Development stock/SPY returns remain unread, protected returns remain unread, the master holdout remains unconsumed, historical supported alpha remains 0, and Phase33 remains blocked.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md`;
4. retained beneficial-ownership source-repair and feasibility records;
5. accepted XBRL closeout/scientific/source records;
6. accepted Phase32 closeout/scientific/source records;
7. `docs/phase_flow.md`, `docs/phase_plain_english_contract.md`, accepted code, validators, exact-head CI/PR evidence, and historical phase records.

## 1. Mission

ATLAS is the **Autonomous Trading, Learning, and Analysis System** and the greenfield successor to Chart Monitor.

> Use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs.

Profit is never guaranteed. ATLAS is judged by defensible positive expected value after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin—not by trade count, alert count, or attractive backtests.

## 2. Locked architecture

`market/reference/regulatory data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Persistent roles:

- Parquet = durable analytical/history lake.
- DuckDB = analytical/query engine.
- PostgreSQL = later persistent operational state after promotion.
- Massive = primary broad-market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive subscription = **Stocks Starter**; no other entitlement is assumed.
- Official SEC EDGAR/XBRL = read-only authoritative regulatory provenance when phase-gated.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = explicit/manual secondary broker; **no automatic broker failover**.
- ML = predictive evidence, never standalone authority.
- AI = independent audit/challenge layer, not unilateral authority.
- Browser GUI = operator surface, never a second trading engine.

## 3. Persistent non-negotiables

1. Alpha remains the critical path while accepted execution/safety foundations already exist.
2. Zero candidates/trades is legitimate; thresholds are never weakened to force activity.
3. PIT data, chronology, realistic costs, leakage controls, dependence-aware statistics, multiplicity controls, protected evidence, and reproducibility are mandatory.
4. No silent self-modification of strategy/model/support/risk authority.
5. Research/community/provider ideas are hypotheses or source claims, not performance evidence.
6. Reuse accepted components rather than creating parallel authority without measured cause.
7. Every numbered phase starts and ends with a plain-English operator explanation.
8. GUI is a product surface, not business-logic authority.
9. Deployment is engineered/tested, not improvised.
10. Fail closed on ambiguous identity, stale/missing data, uncertain mutation state, invalid geometry, unknown broker/order state, or unreconciled exposure.
11. PAPER does not imply LIVE.
12. No automatic cross-broker failover.
13. **Root cause before workaround:** an error stops progression until the cause is diagnosed and a proper correction is implemented/tested. Validators, thresholds, chronology, identity, multiplicity, protected rules, or authority may not be weakened to manufacture PASS.
14. Preserve provider-native ticker text/case and exact PIT identity; ticker alone never proves continuity.
15. No fabricated pre-2021 intraday history.
16. Finalized canonical facts outrank provisional state.
17. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
18. Protected performance is finalist-only. Once a holdout outcome is read, that holdout is consumed for later alpha selection.
19. A legitimate negative research phase may be accepted but cannot satisfy a downstream positive-entry condition.
20. When a research family fails, the next family must change the economic/information mechanism rather than retune the failed family after results.
21. Provider plan/history/entitlement claims require evidence and, where material, empirical verification.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available.
23. Material source/architecture/scientific decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.
24. Long-running target-machine runners should emit lightweight terminal progress; observability may never alter scientific logic.
25. Existing valid source caches are evidence and must not be deleted merely to simplify a repaired rerun.

## 4. Required phase/gate cadence

The roadmap is conditional, not schedule-driven. One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT LARGEST SAFE COHERENT PACKAGE -> FOCUSED TESTS -> ROOT-CAUSE REPAIR IF NEEDED -> COMPLETE EXACT-HEAD FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> POST-MERGE VERIFY -> NEXT PHASE`

Operational rules:

- Do not create conversational approval gates for internal implementation steps that do not change scientific/provider/broker/destructive/LIVE authority.
- Freeze scientific/source policy before reading the outcomes governed by that policy.
- Run focused validation before expensive or broad acceptance tests.
- If a failure occurs, preserve it, diagnose the owning layer, make the narrowest proper repair, add regression coverage, and rerun exact-head certification.
- Never weaken validators or frozen science to obtain PASS.
- Repository CI proves repository properties; target-machine runs remain mandatory for local source/provider/artifact facts CI cannot establish.
- Do not run expensive target evidence against a repository head that has not passed the required exact-head repository certification.
- Negative evidence is valid evidence. A research family can close `ACCEPTED_NEGATIVE` without granting downstream positive authority.

## 5. Accepted foundation through Phase32

Phases1–25 accepted the project/config/session foundation, provider ingestion, canonical Parquet/DuckDB data, PIT identity/history, live market state, deterministic features, universe/discovery/regime/ML/strategy routing, promoted-only deep research, news/options/instrument/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary operations, browser/API primitives, restart-safe orchestration, centralized PAPER authority, and exact historical production-path reconstruction.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

Modern alpha phases:

- Phase26 deterministic/composite self-feature alpha — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional expected-return learning/ranking — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network alpha — `ACCEPTED_NEGATIVE`.
- Phase29 relative-value statistical-arbitrage alpha — `ACCEPTED_NEGATIVE`.
- Phase30 public-news-arrival alpha — `ACCEPTED_NEGATIVE`.
- Phase31 SEC Form-4 insider-transaction alpha — `ACCEPTED_NEGATIVE`.
- Phase32 SEC 8-K material corporate-event alpha — `ACCEPTED_NEGATIVE`.

Phase31 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.

Phase32 merged through PR #37 at `69f8aa81289934b71f2652482c747391917c15a3`. Its frozen protected source-only evidence was **46 event rows / 33 signal sessions / 40 instruments**; the preregistered 50-event-row minimum failed before protected returns were opened. Protected return rows read = 0; holdout consumed = false.

The Phase32 closure requires the next research family to use a **materially different point-in-time fundamental-information mechanism**. Later research may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result. That anti-retuning boundary remains permanent even as the living roadmap advances to later named mechanisms.

Historical supported modern alpha remains **0**.

## 6. Completed pre-Phase33 SEC XBRL mechanism — `ACCEPTED_NEGATIVE`

The SEC XBRL fundamental-quality/accrual program materially changed the information mechanism from Phase32 and used PIT standardized quarterly fundamentals from original SEC 10-Q/10-K filings.

Its source feasibility passed; its first PIT identity audit failure was preserved; a targeted active-common-stock identity repair passed; six finite year-over-year quality-change hypotheses were frozen before outcomes; development then produced **0 selection passers, 0 winners, and 0 internal finalists**. Protected returns were never opened.

Accepted scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

The family merged through PR #38 at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`, followed by green Ubuntu/Windows regression. It is closed to post-result retuning or protected rescue.

## 7. Current pre-Phase33 mechanism — SEC Schedule 13D/13G beneficial ownership

The retained source-feasibility family identifier is:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

The current frozen scientific mechanism, narrowed before outcome access, is:

`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`

### 7.1 Retained source-feasibility history

Parent source-only feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

The original source run is permanently preserved as failed/not accepted. Its owning-layer defects were repaired without market outcomes or relaxed numeric gates.

Targeted source-repair fingerprint:

`78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c`

Accepted v2 source evidence:

- 43/43 quarterly SEC master indexes;
- 200/200 complete submissions parsed;
- 200/200 accession/form/date reconciliations;
- 200/200 authoritative `SUBJECT COMPANY` CIK extractions;
- 195 unique authoritative subject CIKs;
- 200/200 acceptance-derived decision sessions;
- 142 unambiguous PIT active common-stock mappings;
- zero target/protected market outcomes.

The authoritative security issuer is the exact `SUBJECT COMPANY` CIK from the official SEC complete-submission header. Master-index CIK is filing/index provenance only. Decision session is the first XNYS regular-session open strictly after SEC acceptance. Identity uses exact subject CIK + decision date + `active=true` + `type=CS`, with ambiguity failing closed.

### 7.2 Frozen finite science

Scientific contract:

`alpha-gate-beneficial-ownership-scientific-v1-four-initial-ownership-intent-buckets`

Scientific fingerprint:

`4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`

Development implementation fingerprint:

`0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d`

Exactly four non-overlapping LONG hypotheses are frozen before outcomes:

1. `initial_13d_5_to_10_long` — initial Schedule 13D, `5 <= percent < 10`;
2. `initial_13d_10_plus_long` — initial Schedule 13D, `percent >= 10`;
3. `initial_13g_5_to_10_long` — initial Schedule 13G, `5 <= percent < 10`;
4. `initial_13g_10_plus_long` — initial Schedule 13G, `percent >= 10`.

No amendment hypothesis, short hypothesis, alternate ownership threshold, purpose-text taxonomy, reporting-person type filter, or filer-class filter may be added after outcomes.

The filing-level predictor is the maximum valid cover-page percent-of-class across reporting persons, never the sum. Only initial 13D/13G filings are performance eligible.

Frozen primary chronology/performance:

- source window: `2016-01-01..2026-08-11`;
- governed performance start: `2021-08-16`;
- development last signal: `2024-12-31`;
- outer embargo: `2025-01-02..2025-04-03`;
- protected signals: `2025-04-04..2026-05-11`;
- protected outcome end: `2026-08-11`;
- entry: decision-session open;
- primary exit: close 63 XNYS sessions after decision;
- primary performance: stock open-to-63-close minus same-window SPY minus 10 bps LONG cost;
- independent positive after-cost unhedged return also required;
- stress cost: 25 bps;
- 21/126-session paths: diagnostic only.

Frozen statistical governance includes chronological 70/30 development with a 63-session purge, dependence-aware 63-session block bootstrap, global `HOLM_BONFERRONI_GLOBAL_4`, frozen minimum event/session/instrument counts, fold consistency, year/regime/concentration diagnostics, at most one selection winner, internal confirmation only, no runner-up substitution, and finalist-only protected returns. The detailed normative numeric rules remain in `docs/alpha_gate_sec_beneficial_ownership_scientific_contract.md`.

### 7.3 Preserved pre-outcome acquisition failure and repair

The target scientific runner reached **3500/5200** in the source-only predictor walk and stopped before `Source-only predictor reconstruction: PASS` because one legitimate official SEC complete submission exceeded the historical/default 20 MB response ceiling.

At that stop:

- development stock return rows read = 0;
- development SPY return rows read = 0;
- protected return rows read = 0;
- protected holdout consumed = false;
- no candidate performance had been opened.

The existing source cache through approximately 3500 items is valid and must not be deleted.

Frozen development transport-repair fingerprint:

`a4db8419364895c6861c4becbe3abf9b32ec044ceb4aff5cf14a7c9244368bdb`

Transport contract:

- quarterly indexes remain bounded at 64 MB;
- historical/default complete submissions remain bounded at 20 MB;
- scientific acquisition explicitly opts into a bounded 256 MB complete-submission ceiling;
- SEC archive pacing remains 5 calls/second / 0.2-second minimum interval;
- scientific/sample/statistical/protected policy is unchanged.

Compatibility repair code commit:

`8b4a5dc8dc8931062cd34ec30b71b38f82a53a9d`

The provider retains the historical static `_response_limit(url)` seam and isolates the explicit scientific per-client submission override behind `_configured_response_limit(url)`. Focused beneficial-ownership validators and tests pass on Ubuntu and Windows at that code commit. Exact-head full regression after documentation synchronization is required before target execution.

### 7.4 Current progression rule

The next authorized sequence is exact and narrow:

1. exact-head focused beneficial-ownership CI green on Ubuntu and Windows;
2. exact-head full ATLAS regression green on Ubuntu and Windows;
3. target machine updates to that exact branch head while retaining the existing beneficial-ownership source cache;
4. resume `scripts/run_alpha_gate_beneficial_ownership_development.py`;
5. source-only predictor reconstruction must PASS before any development stock/SPY outcomes open;
6. evaluate the four already-frozen hypotheses under the frozen development contract;
7. protected returns remain sealed unless one fixed finalist independently earns access under the frozen source-only protected precheck;
8. close the family scientifically as supported or accepted-negative, document, certify, merge, and only then choose the downstream step.

No new alpha family, threshold change, cache deletion, runner-up substitution, or manual bypass is authorized during this sequence.

## 8. Remaining master roadmap

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** at least one strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

**Current state:** **BLOCKED**, because accepted historical supported alpha = 0.

When eligible, convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted capabilities. No LIVE.

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

## 9. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted-negative science cannot substitute for it. The current critical path remains historical alpha validation until a mechanism earns accepted `SUPPORTED` authority.
