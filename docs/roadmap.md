# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-28 after Phase32 semantic census PASS and corrected pre-performance scientific-contract freeze.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. the active phase specification;
4. `docs/phase32_scientific_contract.md` while Phase32 is active;
5. `docs/phase_flow.md`;
6. `docs/phase_plain_english_contract.md`;
7. accepted code, validators, CI/PR evidence, and historical phase records.

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
- Official SEC EDGAR = read-only authoritative regulatory provenance when phase-gated.
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
20. When a research family fails, the next phase must change the economic/information mechanism rather than retune the failed family after results.
21. Provider plan/history/entitlement claims require evidence and, where material, empirical verification.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available.
23. Material source/architecture/scientific decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

## 4. Accepted foundation through Phase31

Phases1–25 accepted the project/config/session foundation, provider ingestion, canonical Parquet/DuckDB data, PIT identity/history, live market state, deterministic features, universe/discovery/regime/ML/strategy routing, promoted-only deep research, news/options/instrument/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary operations, browser/API primitives, restart-safe orchestration, centralized PAPER authority, and exact historical production-path reconstruction.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

Modern alpha phases:

- Phase26 deterministic/composite self-feature alpha — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional expected-return learning/ranking — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network alpha — `ACCEPTED_NEGATIVE`.
- Phase29 relative-value statistical-arbitrage alpha — `ACCEPTED_NEGATIVE`.
- Phase30 public-news-arrival alpha — `ACCEPTED_NEGATIVE`.
- Phase31 SEC Form-4 insider-transaction alpha — `ACCEPTED_NEGATIVE`.

Retained historical Phase31 rebaseline marker (preserved for accepted validator/provenance continuity): **Active Phase31 — SEC Form-4 Insider-Transaction Alpha**. This marker records the Phase31 active-state handoff and does not supersede the current Phase32 active state below.

Retained Phase31-era downstream marker: **Phase32 — Signal-to-Trade Construction**. This preserves the accepted Phase31 handoff record only; the current roadmap subsequently rebaselined SEC 8-K research as Phase32 and Signal-to-Trade as Phase33.

Phase31 PR #35 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`. Its four frozen candidates produced zero survivors/winners/finalists/support and zero protected reads. The master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.

Validated alpha remains the blocker. Signal-to-trade construction is still forbidden.

## 5. Phase/gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority. Non-performance feasibility may precede hypothesis freeze only when it reads no target outcomes and creates no alpha authority.

## 6. Active Phase32 — SEC 8-K Material Corporate-Event Alpha

**Purpose:** test whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from Phases26–31.

### Accepted source foundation

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Core V2 PASS established Massive original-8-K discovery plus official SEC submissions metadata, exact accession/form/filing-date/acceptance reconciliation, and zero market-outcome reads.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 PASS established taxonomy version 1.0 / 119 rows, 7,468 disclosure rows across five retained probe windows, complete original-8-K accession overlap, independently reconciled SEC samples, source-scope-aware ticker/text semantics, and zero target/protected outcome reads.

### Source/taxonomy census — accepted

The local immutable census passed with 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes. It was source feasibility only.

### Scientific contract — frozen before performance

Corrected policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The earlier proposed `0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88` fingerprint was superseded before acceptance and before any market-outcome read after a pre-performance identity audit aligned the contract with `instrument-identity-v4-no-issuer-level-medium-collapse`.

Exactly **five hypotheses** are frozen:

1. `equity_issuance_short`;
2. `share_repurchase_long`;
3. `financial_integrity_adverse_short`;
4. `listing_distress_short`;
5. `solvency_distress_short`.

The frozen policy fixes exact taxonomy triples and directions; SEC acceptance-time public availability; decision-open entry; five-session exit; SPY-relative and required unhedged outcomes; 0/5/10/25/50-bps cost grid with 10-bps primary and 25-bps stress; 5-session purge/block bootstrap; mandatory sample/concentration gates; global `HOLM_BONFERRONI_GLOBAL_5`; robustness; winner/finalist rules; no runner-up substitution; and finalist-only protected returns.

PIT instrument resolution is bound to the accepted identity-v4 implementation: strong identity = Composite FIGI / Share Class FIGI; medium identity = **CIK + exact provider-native ticker + primary exchange + security type**. Only strong/medium identity is eligible, exactly one CIK-matching instrument must resolve, and ticker+snapshot fallback, current-universe backprojection, and ticker alias backfill are forbidden.

The decision session is operationally the first XNYS session whose regular open timestamp is strictly after official SEC `acceptanceDateTime`.

Development last signal is `2026-05-04`; outer embargo is `2026-05-05..2026-05-11`; protected starts `2026-05-12`; last protected signal with complete five-session outcome is `2026-08-04`; protected outcome end is `2026-08-11`.

No stock/SPY/options return was read to choose this family or methodology.

### Exact active target — full-history predictor/source acquisition

The next permitted Phase32 operation is **full-history** source/predictor acquisition for `2021-08-16..2026-08-11` under the unchanged corrected policy fingerprint.

It must acquire/reconcile original Massive 8-K discovery, accepted semantic disclosure evidence, official SEC acceptance metadata, exact accession/CIK lineage, and point-in-time instrument resolution under identity-v4. It must read **zero market outcomes**.

Only after this full-history predictor/source gate passes may development returns be opened under the exact frozen policy. Protected returns remain finalist-only.

### Authority boundary

Allowed now: accepted immutable source evidence, frozen policy/validators/tests, full-history source/predictor acquisition, PIT instrument mapping, and documentation.

Forbidden: development market outcomes before the predictor/source gate, protected returns before finalists/blindness audit, provider mutations, broker/account reads or writes, orders, PAPER submissions, LIVE writes, automation writes, frontend trading authority, and automatic broker failover.

A source or policy PASS does not establish alpha or satisfy Phase33.

## 7. Remaining master roadmap

### Phase32 — SEC 8-K Material Corporate-Event Alpha

Complete full-history predictor/source acquisition, then evaluate the frozen five-hypothesis family under the locked PIT/after-cost/dependence/multiplicity/robustness/protected-evidence standards. Close either `SUPPORTED` if genuine alpha survives all gates or `ACCEPTED_NEGATIVE` if it does not.

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted Phase12/13/14 capabilities. No LIVE.

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

## 8. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted negative science cannot substitute for it.