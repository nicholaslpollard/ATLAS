# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-31 (America/New_York). Accepted numbered foundation remains through Phase32. The later SEC XBRL, SEC Schedule 13D/13G beneficial-ownership, FINRA consolidated short-interest v1, and SEC diluted-EPS earnings-innovation v1 research families are all scientifically closed accepted-negative. Historical supported alpha remains 0 and Phase33 remains blocked.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_earnings_innovation_source_only_closeout.md` and retained earnings-innovation feasibility/PIT/diagnostic records;
4. `docs/alpha_gate_finra_short_interest_source_only_closeout.md` and retained FINRA scientific/PIT/source records;
5. accepted beneficial-ownership closeout/scientific/source records;
6. accepted XBRL closeout/scientific/source records;
7. accepted Phase32 closeout/scientific/source records;
8. `docs/phase_flow.md`, `docs/phase_plain_english_contract.md`, accepted code, validators, exact-head CI/PR evidence, and historical phase records.

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
20. When a research family fails or closes negative, the next family must change the economic/information mechanism rather than retune the observed family.
21. Provider plan/history/entitlement claims require evidence and, where material, empirical verification.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available.
23. Material source/architecture/scientific decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.
24. Long-running target-machine runners should emit lightweight terminal progress; observability may never alter scientific logic.
25. Existing valid source caches are evidence and must not be deleted merely to simplify a repaired rerun.
26. If multiplicity is frozen across a finite hypothesis family, a source-only failure in one member cannot be repaired after observation by silently dropping that member. A changed family is a new preregistered experiment.
27. A source-only sample insufficiency may close an experiment without opening market outcomes when the frozen acceptance contract cannot be satisfied from the available source population.
28. When an authoritative-source replay reproduces the original source hashes and the same cross-source contradiction/ambiguity, treat it as a source-semantics/provenance limitation rather than local-cache corruption. Preserve raw representations; do not purge/refetch the lake merely to try to make the inconsistency disappear.

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

Phase32 merged through PR #37 at `69f8aa81289934b71f2652482c747391917c15a3` under frozen policy fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.

Exactly five hypotheses were frozen before performance. The frozen finalist was `solvency_distress_short`. Its protected source-only evidence was **46 event rows / 33 signal sessions / 40 unique instruments** versus the frozen **50 / 20 / 20** minimum. Protected stock/SPY returns remain unread; holdout unconsumed.

The Phase32 closure requires a materially different point-in-time fundamental-information mechanism for its immediate successor family. Later research may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result.

Historical supported alpha remains **zero**. Historical supported modern alpha remains **0**.

## 6. Completed Pre-Phase33 SEC XBRL mechanism — `ACCEPTED_NEGATIVE`

Mechanism: `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

Retained source-only feasibility lineage:

- Phase32 source merge: `69f8aa81289934b71f2652482c747391917c15a3`;
- feasibility state: `FEASIBILITY_PASS`;
- feasibility contract: `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
- feasibility fingerprint: `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
- accepted feasibility evidence fingerprint: `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
- retained PIT audit fingerprint: `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`.

- source feasibility: **200** Company Facts docs, **170** accrual-history-ready issuers, **92** profitability-history-ready issuers;
- original PIT audit failure preserved; targeted common-stock active-only identity repair passed without changing source population or numeric gates;
- scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`;
- development: **0 selection passers / 0 winners / 0 internal finalists**;
- protected return rows read: **0**; holdout consumed: **false**;
- closeout evidence fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`;
- merged through PR #38 at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`.

## 7. Completed Pre-Phase33 SEC Schedule 13D/13G beneficial ownership — `ACCEPTED_NEGATIVE`

Source-only feasibility mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.

Frozen feasibility fingerprint: `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.

Scientific mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.

- targeted source repair: **43/43 quarterly indexes**, **200/200 complete submissions**, **195 unique authoritative subject CIKs**, **200 decision sessions**, **142 PIT active common-stock mappings**;
- scientific fingerprint: `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`;
- predictor rows: **3,652** = **2,763 DEVELOPMENT / 889 PROTECTED**;
- usable development outcomes: **2,412**;
- selection passers/winners/internal finalists: **0 / 0 / 0**;
- protected return rows read: **0**; holdout consumed: **false**;
- closeout evidence fingerprint: `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`;
- merged through PR #39 at `208529c5562920cc0b2bcf2bae546e2b9af0a25b`.

The family is permanently closed to post-result ownership-threshold, form/amendment, direction, taxonomy/filter, horizon, cost, sample, multiplicity, winner/finalist, or protected-policy rescue.

## 8. Completed pre-Phase33 FINRA consolidated short interest v1 — `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`

Mechanism: `PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`.

### 8.1 Source feasibility and PIT identity

Feasibility contract:

`alpha-gate-finra-short-interest-feasibility-v1-consolidated-position-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4`

Accepted feasibility result: **12/12 files**, **244,979 total rows**, **137,575 exchange-listed rows**, **20,248 unique exchange-listed symbols**, years 2021–2026, zero market outcomes.

PIT audit fingerprint:

`ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846`

Accepted PIT result: **136,731 immutable exchange-listed rows**, **63,761 PIT-eligible rows**, **8,054 unique PIT instruments**, all **12/12** files above the frozen per-file minimum, zero market outcomes.

### 8.2 Frozen science

Scientific contract:

`alpha-gate-finra-short-interest-scientific-v1-four-position-change-crowding-buckets`

Scientific fingerprint:

`0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`

Exactly four hypotheses were frozen:

1. `rapid_short_build_crowded_short` — SHORT;
2. `rapid_short_build_non_crowded_short` — SHORT;
3. `rapid_short_cover_crowded_long` — LONG;
4. `rapid_short_cover_non_crowded_long` — LONG.

Global multiplicity: `HOLM_BONFERRONI_GLOBAL_4`.

The source-only stage required each hypothesis to meet frozen development minimums **900 rows / 30 signal sessions / 500 unique instruments** and protected minimums **300 rows / 16 signal sessions / 200 unique instruments** before any development performance could open.

### 8.3 Accepted full source-only reconstruction

Accepted source target head:

`d312ec95752ab49a6fcbec18973faacb96d4aa89`

The full **116-settlement** reconstruction processed **116 FINRA files** and **232 Massive PIT snapshots** and produced **19,343** predictor rows: **14,841 DEVELOPMENT / 4,502 PROTECTED**.

Candidate totals:

- `rapid_short_build_crowded_short`: **2,036**;
- `rapid_short_build_non_crowded_short`: **8,025**;
- `rapid_short_cover_crowded_long`: **1,257**;
- `rapid_short_cover_non_crowded_long`: **8,025**.

All source gates passed except:

`rapid_short_cover_crowded_long -> protected_min_rows`

Its protected source population was **257 event rows / 26 signal sessions / 211 unique instruments** versus frozen minimums **300 / 16 / 200**. Thus the exact failure was **257 < 300 rows** while session and instrument support passed.

The source-only predictor returned `SOURCE_ONLY_PREDICTOR_FAIL` and stopped. Development/target market outcome rows read = **0**. Protected return rows read = **0**. Holdout consumed = **false**.

Accepted predictor report SHA-256:

`56479707945a59752aeb2056f3cfbcfd2df1e4a87ada31c9e8e6d3ed93f314cd`

Accepted predictor rows SHA-256:

`21c7dd2e44013ba0f1d290019db70f7b0f23b0603c5e965cbd8b441128190e48`

Accepted persisted-artifact probe head:

`5ceac74ad67c8f3539b03192cf1946d51d476434`

Accepted probe evidence fingerprint:

`c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce`

Accepted closeout evidence fingerprint:

`bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`

Final disposition:

`ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`

This is a source-capacity negative, not a performance negative. No return or alpha-performance claim is authorized because market outcomes were never opened.

### 8.4 Permanent anti-retuning boundary

The exact FINRA v1 experiment cannot be rescued by dropping `rapid_short_cover_crowded_long`, lowering the 300-row protected floor, changing the 10% change-tail or 80% crowding thresholds, changing deterministic sampling, chronology, horizon, costs, folds, dependence treatment, multiplicity, direction, bucket definitions, or protected policy after observing the source result.

A future short-interest experiment, if any, must be a newly preregistered scientific version before outcomes.

## 9. Completed pre-Phase33 SEC diluted-EPS earnings innovation v1 — `ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`

Mechanism: `PIT_SEC_XBRL_DILUTED_EPS_SEASONAL_EARNINGS_INNOVATION_POST_PERIODIC_FILING_DRIFT`.

Feasibility passed source-only on a deterministic 300-CIK sample with 300/300 Company Facts successes, **5,905** direct-quarter observations, **204** issuers with at least 12 direct quarters, **170** with at least 16, years **2013–2026**, and no market outcomes.

Frozen feasibility fingerprint:

`c32e4aa83b25cdc23476098ffc30bd48908123d047d75f18f0d45b2acaffcd0d`

Frozen PIT audit fingerprint:

`423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa`

The PIT audit required the earliest retained non-amendment periodic-filing accession to have an unambiguous direct-quarter context/value and required accession/form/filing date to reconcile exactly against official SEC Submissions metadata.

The first PIT audit preserved **5,902** original-accession candidates and **5,896** audited observations, but failed exactly two zero-tolerance gates:

- **3 ambiguous earliest period contexts**;
- **6 accession/form/filing-date contradictions**.

All other frozen PIT source gates passed. Target outcome rows read = **0**. Protected return rows read = **0**. Holdout consumed = **false**.

The V2 source-only diagnostic re-fetched all 300 Company Facts documents and reproduced **300/300 exact Gate0 hashes**. It re-read official SEC Submissions metadata for all 300 issuers and reproduced the same six contradictions with zero missing accession metadata. Diagnostic fingerprint:

`399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961`

This establishes a source-semantics/provenance limitation, not local ATLAS data corruption. Blind cache/lake deletion or refetch is not an authorized repair: a clean official-source replay already reproduced the evidence. Raw official representations remain preserved.

Three contradictions were filing-date mismatches despite matching accession/form; three represented facts as `10-Q` in Company Facts while official Submissions identified the accession as `10-Q/A`. The ambiguous period cases contained multiple qualifying contexts in the same earliest accession; two also carried different diluted-EPS values.

Because the frozen v1 contract explicitly requires unambiguous context/value and exact metadata reconciliation, selecting a preferred context, tolerating date drift, reclassifying amendments, dropping offending rows, or relaxing zero-tolerance gates after seeing these records would be post-result retuning.

Closeout fingerprint:

`29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`

Final disposition:

`ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`

No performance claim is authorized because market outcomes were never opened. Any future SEC XBRL mechanism may define different reconciliation/canonicalization semantics only prospectively under a new preregistration.

## 10. Remaining master roadmap

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** at least one strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

**Current state:** **BLOCKED**, because accepted historical supported alpha = 0.

When eligible, convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted capabilities. No LIVE.

### Phase34 — End-to-End Historical Replay & Stress Certification + Replay Dashboard

Replay the frozen supported system as one account-level process and certify net expectancy, drawdown/tail loss, costs, concentration, capacity, regime/year behavior, and stress outcomes.

### Phase35 — Prospective SHADOW/PAPER Certification + Operator Web Beta

Operate on genuinely new unseen sessions with SHADOW and Webull-primary PAPER. LIVE remains unavailable.

### Phase36 — Outcomes, Learning, Drift Monitoring & Governance + Performance UI

Trace decisions/trades/outcomes to exact data/model/strategy/risk versions and monitor calibration, economics, slippage, and degradation. Learning never silently self-authorizes changes.

### Phase37 — Production Web Application, Operations & Deployment

Consolidate the production web application and accepted Python engine; promote PostgreSQL operational state/autonomous scheduling only with proven parity, recovery safety, idempotency, and auditability.

### Phase38 — LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification

**No LIVE authority yet.** Harden stale-data, provider/broker outage, partial-fill, cancel/replace, API/UI/network/database/restart, duplicate-prevention, buying-power drift, reconciliation, emergency-disable/flatten, and manual-broker-fallback behavior.

### Phase39 — Controlled LIVE Activation & Evidence-Based Scaling

Enable LIVE only through explicit authorization with deliberately small initial exposure, hard risk/loss limits, reconciliation/health, kill capability, manual fallback, and no automatic broker failover. Scale only from evidence.

## 11. Progression rule

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted-negative science cannot substitute for it.

The current critical path remains historical alpha validation. The next research family must use a **materially different economic/information mechanism** from the now-closed SEC diluted-EPS earnings-innovation v1 and prior accepted-negative families; none may be rescued by post-result source-rule, threshold, feature, direction, sample, multiplicity, or protected-policy changes.
