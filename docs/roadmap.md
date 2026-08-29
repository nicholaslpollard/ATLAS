# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-28 after Phase32 corrected semantic V2 source qualification PASS.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. the active phase specification;
4. `docs/phase_flow.md`;
5. `docs/phase_plain_english_contract.md`;
6. accepted code, validators, CI/PR evidence, and historical phase records.

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
- Official SEC EDGAR may be used read-only for authoritative regulatory provenance when phase-gated.
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
13. **Root cause before workaround:** an error stops progression until the cause is diagnosed and a proper correction is implemented/tested. Validators, thresholds, chronology, identity, multiplicity, protected rules, or authority may not be weakened to manufacture PASS. A different method is considered only after the intended method is shown infeasible.
14. Preserve provider-native ticker text/case and exact PIT identity; ticker alone never proves continuity.
15. No fabricated pre-2021 intraday history.
16. Finalized canonical facts outrank provisional state.
17. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
18. Protected performance is finalist-only. Once a holdout outcome is read, that holdout is consumed for later alpha selection.
19. A legitimate negative research phase may be accepted but cannot satisfy a downstream positive-entry condition.
20. When a research family fails, the next research phase must change the economic/information mechanism rather than retune the failed family after results.
21. Provider plan/history/entitlement claims require evidence and, where material, empirical verification.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available, otherwise use a conservative later boundary.
23. Material phase/source/architecture decisions and completed gates must be synchronized into the roadmap, current status, active phase docs, and README as applicable before work is considered complete.

## 4. Accepted foundation through Phase31

Phases1–25 accepted the project/config/session foundation, provider ingestion, canonical Parquet/DuckDB data, PIT identity/history, live market state, deterministic features, universe/discovery/regime/ML/strategy routing, promoted-only deep research, news/options/instrument/geometry/portfolio-risk planning, independent AI audit, broker-neutral SHADOW/PAPER execution, Webull-primary/Alpaca-manual-secondary operations, browser/API primitives, restart-safe orchestration, centralized PAPER authority, and exact historical production-path reconstruction.

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and Massive from `2021-08-16` onward. No synthetic pre-2021 1h/4h history exists.

Phase11 strategy authority remains SUPPORTED **0**; MIXED `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`; UNSUPPORTED `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Modern alpha phases:

- Phase26 deterministic/composite self-feature alpha — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional expected-return learning/ranking — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network alpha — `ACCEPTED_NEGATIVE`.
- Phase29 relative-value statistical-arbitrage alpha — `ACCEPTED_NEGATIVE`.
- Phase30 public-news-arrival alpha — `ACCEPTED_NEGATIVE`.
- Phase31 SEC Form-4 insider-transaction alpha — `ACCEPTED_NEGATIVE`.

Phase31 PR #35 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`. Development predictor/usable rows were **5,400 / 5,371**; all four frozen candidates failed mandatory gates; zero survivors/winners/finalists/support; zero protected reads. The master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.

Validated alpha remains the blocker. Signal-to-trade construction is still forbidden.

## 5. Phase/gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority. Non-performance feasibility may precede hypothesis freeze only when it reads no target outcomes and creates no alpha authority.

## 6. Active Phase32 — SEC 8-K Material Corporate-Event Alpha

**Purpose:** test whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from Phases26–31.

### Core source feasibility — accepted

Phase32 first attempted official SEC archive/header presentation paths. Six source attempts failed without reading any market outcomes. Those failures are retained in `docs/phase32_sec_edgar_access_incident.md`; ATLAS diagnosed the source format and formally versioned the replacement rather than weakening validation.

Accepted V2 source contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS** with 6,048 Massive original-8-K index rows, 5,272 ticker-linked rows, 48 independently reconciled official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted source architecture:

1. discover original `8-K` filings through Massive `GET /stocks/filings/vX/index`;
2. obtain authoritative structured metadata from official `data.sec.gov/submissions/CIK##########.json`;
3. for older filings, follow only SEC-declared date-matching historical submissions shards, maximum two candidates per lookup;
4. independently reconcile exact accession, original `8-K`, filing date, acceptance timestamp, item codes, and CIK provenance;
5. preserve immutable sampled source evidence.

Public-availability rule remains:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

### Semantic source qualification — V2 accepted

SEC item codes are legal filing categories and can group economically different events, so Phase32 additionally qualified Massive semantic 8-K disclosures/text/taxonomy.

Semantic V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1 is retained `NOT ACCEPTED`. Root-cause diagnosis showed that exact cross-endpoint ticker equality and exact `supporting_text` substring-in-`items_text` were invalid provider-scope invariants. V1 remains immutable failed source-only evidence.

Corrected semantic V2 contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Accepted fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Empirical semantic research boundary:

`2021-08-16`

Target-machine V2 result: **PASS** with taxonomy version 1.0 / 119 rows, 7,468 disclosure rows across five retained probe windows, complete original-8-K accession overlap in every window, 30 sampled Massive Text records, 30 independently reconciled SEC records, and zero target/protected outcome reads. Ticker mapping relations were recorded as 22 direct disclosure/index overlaps, 2 historical-map differences where disclosure/text agreed, and 6 fully unmapped samples.

Accepted semantic filing identity is exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker is mapping metadata only. `supporting_text` must be nonblank and taxonomy-linked; `items_text` lexical comparison is diagnostic only.

### Active pre-return source/taxonomy census

Before hypotheses are frozen, ATLAS runs:

`scripts/run_phase32_semantic_v2_source_census.py`

This census is local-only. It hash-checks the accepted V2 taxonomy/disclosure artifacts, makes zero network calls, reads zero stock/SPY/options outcomes, and reports source coverage by primary/secondary/tertiary taxonomy category. Its counts are non-performance feasibility evidence only and cannot establish alpha.

### Scientific-contract freeze after census

Only after the census passes may ATLAS freeze the finite event hypothesis family and the complete scientific contract: directions, event aggregation/contradiction/amendment rules, **point-in-time instrument resolution**, decision session, horizons, benchmark, costs, mandatory sample/concentration gates, dependence-aware inference, multiplicity, robustness, development/internal/protected chronology and purge, winner/finalist/no-runner-up rules, and finalist-only protected read.

No development return may be inspected before that freeze. Semantic ticker metadata is not sufficient by itself for market-outcome linkage; PIT instrument resolution must be separately frozen before any outcome read.

### Authority boundary

Allowed now: accepted immutable 8-K source evidence, local source/taxonomy census, validators/tests, and scientific-contract construction from source semantics.

Forbidden: stock/SPY/options outcomes, protected returns, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

A source PASS does not establish alpha or satisfy Phase33.

## 7. Remaining master roadmap

### Phase32 — SEC 8-K Material Corporate-Event Alpha

Complete the local source/taxonomy census, freeze the full scientific contract, construct predictor-only event evidence, then evaluate the bounded event family under PIT/after-cost/dependence/multiplicity/robustness/protected-evidence standards.

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
