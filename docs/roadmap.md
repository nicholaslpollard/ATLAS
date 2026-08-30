# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-29 after Phase32 full-history predictor/source acquisition and independent local source/predictor acceptance both passed with zero Phase32 market-outcome reads. The next gate is development-only performance evaluation; protected returns remain unread.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. `docs/phase32_sec_8k_material_event_alpha.md`;
4. `docs/phase32_scientific_contract.md`;
5. `docs/phase32_predictor_independent_acceptance.md`;
6. `docs/phase32_development_evaluation.md`;
7. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
8. accepted code, validators, CI/PR evidence, and historical phase records.

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
24. Long-running target-machine runners should emit lightweight progress such as `x / total completed`; progress reporting is observability only and may not alter scientific or authority logic.

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

Retained historical Phase31-era validator/provenance markers, **not current numbering or authority**: `Active Phase31 — SEC Form-4 Insider-Transaction Alpha`; `Phase32 — Signal-to-Trade Construction`; `Phase38 — Controlled LIVE Activation`. Current rebaselining supersedes those phase numbers without rewriting accepted history.

Phase31 PR #35 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`. It produced zero survivors/winners/finalists/support and zero protected reads. The master protected outcome window `2026-05-12..2026-08-11` remains unconsumed.

Validated alpha remains the blocker. Signal-to-trade construction is still forbidden.

## 5. Phase/gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority. Non-performance feasibility may precede hypothesis freeze only when it reads no target outcomes and creates no alpha authority.

## 6. Active Phase32 — SEC 8-K Material Corporate-Event Alpha

**Purpose:** test whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from Phases26–31.

### Accepted source/scientific foundation

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

The source/taxonomy census passed with 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes.

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses are frozen:

1. `equity_issuance_short`;
2. `share_repurchase_long`;
3. `financial_integrity_adverse_short`;
4. `listing_distress_short`;
5. `solvency_distress_short`.

The frozen policy fixes SEC acceptance-time public availability, decision-open entry, five-session exit, SPY-relative primary plus required unhedged outcomes, 10-bps primary / 25-bps stress costs, 75% chronological selection, five-session purge, 6/3/3 folds, five-session block bootstrap, mandatory sample/robustness/concentration gates, global `HOLM_BONFERRONI_GLOBAL_5`, one winner/finalist per direction, no runner-up substitution, and finalist-only protected returns.

PIT identity is bound to `instrument-identity-v4-no-issuer-level-medium-collapse`: strong identity = Composite FIGI / Share Class FIGI; medium = CIK + exact provider-native ticker + primary exchange + security type. Only strong/medium is eligible, exactly one CIK-matching instrument must resolve, and fallback ticker+snapshot, current-universe backprojection, and ticker alias backfill are forbidden.

### Full-history source/predictor acquisition — ACCEPTED PASS

The target machine completed **36,309** filing entities and produced **19,792** eligible predictors: **18,819 development** and **973 protected-predictor-only**. It read zero stock/SPY/options/protected returns.

Accepted filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Accepted predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

Retained source corrections before outcomes include joint/multi-filer filing-entity handling, strict ticker-only Massive Text multiplicity, targeted crash-cache quarantine/reacquisition, and bounded one-day SEC-declared shard rollover handling. These corrections changed no scientific rule. Detailed evidence remains in the Phase32 incident docs.

### Independent local source/predictor acceptance — ACCEPTED PASS

Contract:

`phase32-predictor-independent-acceptance-v1-local-immutable-source-only`

The corrected independent audit reprocessed all 36,309 filing entities, reproduced both accepted hashes, rebuilt predictor output byte-for-byte, used zero network reads, and read zero stock/SPY/options/protected returns.

Independent acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

The first audit stop was a validator-only exact-byte bug: generic whitespace normalization stripped a canonical SEC source-record trailing LF before hashing. Read-only diagnosis proved the source evidence was correct; exact-byte hashing was fixed without rewriting source data or changing science.

### Exact active target — development-only performance evaluation

The next permitted Phase32 operation is the development-only performance gate documented in `docs/phase32_development_evaluation.md` and implemented by `scripts/run_phase32_development.py`.

This is the first Phase32 operation authorized to read **development** stock/SPY outcomes. Before that one-way boundary it must pin the independent acceptance fingerprint, source report, predictor/evidence hashes, exact stage partition, exact source-derived execution ticker for every development predictor, and accepted split/corporate-action evidence. Missing or ambiguous execution-ticker lineage must fail before outcomes; market-data availability may never resolve identity ambiguity.

The development study then uses exact decision-session open and t+5 close stock/SPY bars, accepted split-crossing censoring, previous-session accepted market/ticker regimes, the frozen selection/internal gates, fixed folds, Holm-5, one winner per direction, no runner-up substitution, and at most one finalist per direction.

Protected stock/SPY returns remain unread. If there are zero finalists, next is independent negative closeout with the holdout unconsumed. If finalists exist, next is a separate independent blindness/lineage audit and immutable finalist-only protected plan; protected returns are still not opened by development evaluation.

### Authority boundary

Allowed now: accepted source/predictor artifacts, frozen policy, local development market-outcome evaluation, local derived development artifacts, validators/tests, and documentation.

Forbidden: protected returns before finalists and a separate blindness/lineage audit; provider mutations; broker/account reads/writes; orders; PAPER; LIVE; automation writes; frontend trading authority; automatic broker failover; and Phase33 signal-to-trade authority.

A development-study PASS means only that the governed test executed correctly. It does not itself establish alpha.

## 7. Remaining master roadmap

### Phase32 — SEC 8-K Material Corporate-Event Alpha

Run the development-only selection/internal gate under the frozen contract. If no finalists survive, close independently `ACCEPTED_NEGATIVE` without protected reads. If finalists survive, perform the independent blindness/lineage audit and finalist-only protected confirmation. Close `SUPPORTED` only if genuine alpha survives every frozen gate.

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

Convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted capabilities. No LIVE.

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
