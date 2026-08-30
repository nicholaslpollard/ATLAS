# ATLAS Master Mission and Roadmap

**Normative project source of truth. Re-synchronized: 2026-08-30 (America/New_York) after completion of the materially different pre-Phase33 SEC XBRL fundamental-quality/accrual research program as `ACCEPTED_NEGATIVE`. Phase32 remains closed and merged. Protected stock/SPY returns remain unread and the master holdout remains unconsumed. Historical supported alpha remains 0; Phase33 signal-to-trade remains blocked.**

Continuation precedence:

1. this roadmap;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_xbrl_closeout.md`;
4. `docs/alpha_gate_sec_xbrl_fundamental_quality.md`;
5. `docs/alpha_gate_sec_xbrl_scientific_contract.md`;
6. `docs/alpha_gate_sec_xbrl_development.md`;
7. `docs/alpha_gate_sec_xbrl_pit_audit.md` and `docs/alpha_gate_sec_xbrl_pit_identity_repair.md`;
8. `docs/phase32_closeout.md` and retained Phase32 source/scientific records;
9. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
10. accepted code, validators, CI/PR evidence, and historical phase records.

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

Phase32 tested structured timestamped SEC 8-K material corporate-event disclosures under frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses were frozen before performance: `equity_issuance_short`, `share_repurchase_long`, `financial_integrity_adverse_short`, `listing_distress_short`, and `solvency_distress_short`.

Accepted source/predictor fingerprints:

- core V2: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`;
- semantic V2: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`;
- independent acceptance: `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

Development produced one finalist, `solvency_distress_short`. Independent finalist blindness/lineage audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

Frozen protected source-only population = **46 event rows / 33 signal sessions / 40 unique instruments**, versus minimum **50 / 20 / 20**. The event-row gate failed before protected performance was opened. Protected return rows read = 0; holdout consumed = false.

Phase32 is `ACCEPTED_NEGATIVE`. Threshold relaxation, alternate finalist substitution, and post-result horizon/taxonomy retuning are forbidden.

Historical supported alpha remains **0**. Phase33 remains blocked.

## 7. Completed Pre-Phase33 SEC XBRL Fundamental Quality / Accrual Mechanism — `ACCEPTED_NEGATIVE`

This mechanism was deliberately a **materially different point-in-time fundamental-information mechanism** from Phase32. It examined standardized original 10-Q/10-K XBRL facts and **may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result** as scientific evidence.

### Source feasibility — accepted PASS

Contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Target head:

`5a8c15f95417390d0d64ff240977adfb38a20c45`

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

Result: `FEASIBILITY_PASS` with 200/200 successful Company Facts documents, 170 accrual-history-ready issuers, 92 profitability-history-ready issuers, and zero market/protected outcome reads.

### PIT audit v1 — preserved FAIL

Frozen audit contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Frozen audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

The first target audit is preserved `AUDIT_FAIL`: 139 unambiguous PIT mappings and 28 issuers with >=3 mappings, against frozen minimum 30. No source or scientific threshold was weakened.

### Targeted identity repair — accepted PASS

Root cause was identity-universe expansion from historical Massive `active=false` plus non-common-stock types. The proper owning-layer repair used exact historical CIK/date plus `active=true` and `type=CS`, retaining the same issuer/accession/SEC chronology/gate population.

Repair fingerprint:

`e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f`

Corrected v2 result: `AUDIT_PASS`, 171 unambiguous common-stock mappings and 38 issuers with >=3 mappings, zero provider calls during replay, zero market/protected outcomes. The v1 failure remains preserved evidence.

### Frozen scientific contract

Scientific contract:

`alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses`

Scientific fingerprint:

`2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`

Exactly six hypotheses were frozen before outcomes: year-over-year improvement/deterioration in gross profitability, cash profitability, and accrual quality, with preregistered LONG/SHORT directions.

The contract fixed PIT quarter reconstruction, exact acceptance/decision chronology, 63-session primary horizon, SPY-relative plus required unhedged outcomes, realistic direction-specific costs, 70/30 chronological development partition with 63-session purge, dependence-aware bootstrap, global `HOLM_BONFERRONI_GLOBAL_6`, robustness and concentration gates, one winner per direction using selection evidence only, internal confirmation only, no runner-up substitution, and finalist-only protected performance.

Development implementation fingerprint:

`3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f`

### Accepted development-negative result

Accepted target head:

`58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`

Result: `ACCEPTED_NEGATIVE_DEVELOPMENT`.

- predictor rows: **5,536**;
- development predictor rows: **4,157**;
- protected predictor rows: **1,379**;
- usable development outcome rows: **3,963**;
- selection passers after all hard gates plus Holm: **0**;
- selection winners: **0**;
- internal finalists: **0**;
- protected-return eligible finalists: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- Phase33 authority: **false**.

Zero candidates survived the frozen development screen. Protected performance was never opened.

### Accepted negative closeout

Closeout contract:

`alpha-gate-xbrl-closeout-v1-development-negative-protected-unread`

Accepted closeout evidence fingerprint:

`291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`

Accepted artifact SHA-256 values:

- development report: `50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6`;
- predictor report: `246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16`;
- predictor rows: `9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a`;
- development outcomes: `17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55`;
- finalists: `c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f`.

Final disposition: **`ACCEPTED_NEGATIVE`**. The family may not be rescued after results by altering feature definitions, directions, costs, horizon, thresholds, multiplicity, winner rules, issuer population, or protected policy.

Historical supported alpha remains **0**. Phase33 remains blocked. The master protected window `2026-05-12..2026-08-11` remains unconsumed.

## 8. Remaining master roadmap

### Next pre-Phase33 alpha research

**Entry condition:** the closed XBRL mechanism is fully merged and post-merge regression is green.

**Mechanism rule:** choose a materially different economic/information mechanism from the closed XBRL year-over-year fundamental-quality/accrual family. Do not retune the closed family under a new label. Source feasibility, scientific policy, and protected boundaries must again be frozen before governed performance as applicable.

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
