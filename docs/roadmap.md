# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-29 (America/New_York) after Phase32 merged `ACCEPTED_NEGATIVE` at `69f8aa81289934b71f2652482c747391917c15a3`. Protected stock/SPY returns remain unread and the holdout remains unconsumed. Historical supported alpha remains 0; Phase33 signal-to-trade remains blocked. The materially different pre-Phase33 SEC XBRL fundamental-quality/accrual mechanism has passed source-only feasibility and is now in a frozen source-only PIT chronology/restatement/identity audit with zero market outcomes.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_xbrl_fundamental_quality.md`;
4. `docs/alpha_gate_sec_xbrl_pit_audit.md`;
5. `docs/phase32_closeout.md`;
6. `docs/phase32_sec_8k_material_event_alpha.md`;
7. `docs/phase32_scientific_contract.md`;
8. `docs/phase32_predictor_independent_acceptance.md`;
9. `docs/phase32_development_evaluation.md`;
10. `docs/phase32_finalist_blindness_audit.md`;
11. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
12. accepted code, validators, CI/PR evidence, and historical phase records.

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
20. When a research family fails, the next phase must change the economic/information mechanism rather than retune the failed family after results.
21. Provider plan/history/entitlement claims require evidence and, where material, empirical verification.
22. Regulatory event dates are not automatically decision timestamps; authoritative publication/acceptance time controls where available.
23. Material source/architecture/scientific decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.
24. Long-running target-machine runners should emit lightweight terminal progress; observability may never alter scientific logic.

## 4. Accepted foundation through Phase32

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

Phase31 PR #35 merged at `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.

Phase32 PR #37 merged at `69f8aa81289934b71f2652482c747391917c15a3`. The merge was accepted only after the target-machine closeout PASS and exact-head Ubuntu/Windows dedicated Phase32 plus full ATLAS regressions passed.

Historical supported alpha remains **zero**.

## 5. Phase/gate model

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Research may close `ACCEPTED_NEGATIVE`, but negative evidence grants no missing downstream authority. Non-performance feasibility may precede hypothesis freeze only when it reads no target outcomes and creates no alpha authority.

Use the **largest safe coherent work package**. Do not turn internal implementation steps into conversational approval gates when they do not change scientific, provider, broker, destructive, or LIVE authority. Target-machine checkpoints remain mandatory where repository CI cannot establish local provider/data/artifact facts.

## 6. Phase32 — SEC 8-K Material Corporate-Event Alpha — `ACCEPTED_NEGATIVE`

**Purpose:** test whether structured, timestamped SEC 8-K material corporate-event disclosures contain robust after-cost post-disclosure return information distinct from Phases26–31.

### Frozen science

Scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses were frozen before performance: `equity_issuance_short`, `share_repurchase_long`, `financial_integrity_adverse_short`, `listing_distress_short`, and `solvency_distress_short`.

The policy fixed SEC acceptance-time public availability, decision-open entry, five-session close exit, SPY-relative primary plus required unhedged outcomes, 10-bps primary / 25-bps stress costs, 75% chronological selection, five-session purge, 6/3/3 folds, five-session block bootstrap, mandatory sample/robustness/concentration gates, global `HOLM_BONFERRONI_GLOBAL_5`, one winner/finalist per direction, no runner-up substitution, and finalist-only protected returns.

PIT identity remained bound to `instrument-identity-v4-no-issuer-level-medium-collapse`.

### Accepted source/predictor foundation

Core V2 fingerprint: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`.

Semantic V2 fingerprint: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`.

Independent source/predictor acceptance fingerprint: `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

The accepted full-history acquisition completed 36,309 filing entities and 19,792 eligible predictors: 18,819 development and 973 protected-predictor-only. Acquisition read zero stock/SPY/options/protected outcomes.

### Development evidence

All five candidates passed selection plus global Holm-5. The frozen one-per-direction winners were `share_repurchase_long` and `solvency_distress_short`.

Internal validation rejected `share_repurchase_long` on its required 90% primary LCB and accepted `solvency_distress_short` with 303 rows, 186 sessions, 219 instruments, 10-bps SPY-relative mean `0.03760873`, unhedged mean `0.03134181`, and 90% LCB `0.01713014`.

Exactly one development finalist was frozen: `solvency_distress_short`.

### Independent finalist blindness / lineage audit — ACCEPTED PASS

The independent finalist blindness/lineage audit reproduced the complete accepted development path without importing the development implementation and then froze a source-only protected plan.

Audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

Frozen source-only protected population = **46 event rows / 33 signal sessions / 40 unique instruments**.

Frozen minimum = **50 / 20 / 20**.

The event-row gate therefore fails before protected performance is opened. Audit status: `AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`.

**Protected stock/SPY returns remain unread.** Protected return rows read = 0. Protected holdout consumed = false.

### Final disposition

Phase32 is `ACCEPTED_NEGATIVE`. The finalist did not earn `SUPPORTED` authority because the frozen protected sample cannot meet a mandatory preregistered source-only requirement. Threshold relaxation, alternate finalist substitution, and post-result horizon/taxonomy retuning are forbidden.

Historical supported alpha remains **0**. Phase33 remains blocked.

## 7. Pre-Phase33 Alpha Gate — SEC XBRL Fundamental Quality / Accrual Mechanism — `FEASIBILITY_PASS; PIT AUDIT OPEN`

**Purpose:** establish a materially different point-in-time fundamental-information mechanism before any market outcome is opened.

This mechanism targets profitability, cash-vs-accrual quality, and fundamental change from standardized original 10-Q/10-K facts. It may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result.

### Source feasibility — accepted

Feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Authoritative route: official SEC `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` through the accepted SEC EDGAR HTTP/fair-access seam.

The deterministic census used exactly 200 unique issuer CIKs selected by SHA-256 ordering from the accepted Phase32 source inventory. This reuse was limited to CIK discovery and granted no Phase32 scientific/performance authority.

The target-machine census on exact head `5a8c15f95417390d0d64ff240977adfb38a20c45` returned **`FEASIBILITY_PASS`**:

- source inventory unique CIKs = **4,400**;
- sample = **200**;
- successful Company Facts documents = **200**;
- failures = **0**;
- accrual-history-ready issuers = **170**;
- profitability-history-ready issuers = **92**;
- group history-ready counts = assets 174, cost of revenue 97, gross profit 78, net income 180, operating cash flow 180, revenue 136;
- target outcome rows read = **0**;
- protected return rows read = **0**;
- protected holdout consumed = **false**;
- provider reads/writes = **200 / 0**;
- broker/order/PAPER/LIVE/automation activity = **0**.

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

### Current source/chronology gate — PIT audit

Frozen audit contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Frozen audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

Exactly 40 deterministic feasibility-ready issuers are audited. Up to 5 clean original `10-Q`/`10-K` accessions per issuer are selected at evenly spaced positions across the historical filing span.

Company Facts supplies exact fact/accession associations. Official SEC submissions metadata supplies exact filing form/date and `acceptanceDateTime`. Later comparative or revised facts remain separate accession versions and can never overwrite an earlier accession's historical state. Contradictory values for the same semantic context inside one accession fail closed.

PIT security identity uses Massive `/v3/reference/tickers` with exact CIK and date at the first XNYS session open strictly after SEC acceptance. The accepted `instrument-identity-v4-no-issuer-level-medium-collapse` contract remains in force; zero or multiple eligible unique instruments fail closed rather than being guessed.

Frozen source-only audit gates require:

- exactly 40 audit issuers;
- >=36 successful Company Facts documents;
- >=180 selected original filings;
- >=170 exact SEC metadata reconciliations;
- >=170 reconstructed acceptance-time decision sessions;
- >=120 unambiguous PIT instrument mappings;
- >=30 issuers with at least 3 unambiguous mappings;
- zero same-accession semantic-context conflicts.

**No alpha hypothesis is frozen. No market price/return, target outcome, or protected return is authorized.** Provider writes, broker/order/PAPER/LIVE/automation authority remain zero.

An `AUDIT_PASS` can authorize only the next scientific freeze work package. Before any governed performance read, ATLAS must freeze a finite hypothesis family, outcomes, costs, chronology, dependence, multiplicity, robustness, sample/concentration gates, winner/finalist rules, and protected-evidence policy. An `AUDIT_FAIL` must be diagnosed without weakening the frozen source or ambiguity rules.

See `docs/alpha_gate_sec_xbrl_fundamental_quality.md` and `docs/alpha_gate_sec_xbrl_pit_audit.md`.

## 8. Remaining master roadmap

### Phase33 — Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype

**Entry condition:** >=1 strategy/alpha model has accepted historical analytical `SUPPORTED` authority.

**Current state:** BLOCKED because accepted historical supported alpha = 0.

When eventually eligible, convert supported evidence into PASS versus trade, stock versus option/defined-risk structure, entry, invalidation/stop, target/exit, horizon/DTE, quantity, and portfolio admission using accepted capabilities. No LIVE.

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

The roadmap is **conditional, not schedule-driven**. Phase numbers do not guarantee advancement. Positive downstream authority requires the exact frozen entry condition; accepted negative science cannot substitute for it.