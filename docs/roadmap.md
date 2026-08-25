# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This document is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but data-integrity, validation, model, strategy, provider, broker, automation, and LIVE authority boundaries change only through an explicit documented and independently validated replacement decision.

For exact continuation read [`current_status.md`](current_status.md). For Phase23 read [`phase23_operational_current_analysis_cycle.md`](phase23_operational_current_analysis_cycle.md). For Phase22 read [`phase22_operational_paper_runner.md`](phase22_operational_paper_runner.md). For Phase21 authority read [`phase21_unified_paper_execution_authority.md`](phase21_unified_paper_execution_authority.md). For development cadence read [`phase_flow.md`](phase_flow.md).

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, identity, features, and regimes;
3. discover candidates cheaply before expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject deterministic cases to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade LIVE only under separately accepted authority;
10. learn descriptively from outcomes without silently changing model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority;
12. orchestrate restart-safe runs without silently creating provider, broker, scheduler, database-runtime, or LIVE authority;
13. operate on current finalized market evidence routinely rather than remaining pinned to a historical acceptance date;
14. reach a complete safe end-to-end PAPER/SHADOW system before lower-value infrastructure work displaces that objective.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute/provider roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; not an accepted runtime prerequisite.
- **Massive**: primary broad-market/reference-data provider path.
- **Webull**: primary PAPER/sandbox execution broker; future LIVE only under a separate explicit authority phase.
- **Alpaca**: manually selectable secondary/fallback; never automatic failover.

### 2.1 Strategic anti-drift anchor

The roadmap destination is the **operational end-to-end ATLAS system**, not any individual infrastructure phase. ATLAS must progress from broad-market discovery through point-in-time evidence, deterministic research/risk planning, and independent AI audit into safe **Webull-primary SHADOW/PAPER execution**, exact reconciliation, observability, and outcome learning before any separately authorized LIVE transition.

Infrastructure, storage, orchestration, scheduling, and control-plane work are justified only when they materially improve correctness, safety, evidence quality, recoverability, performance, or operability. A technically interesting but lower-value infrastructure task must not displace the current end-to-end objective by silent drift.

## 3. Mandatory phase execution contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Principles:

- code existence or passing tests alone is not acceptance;
- credentials/configuration/connectivity never silently expand provider, broker, automation, or LIVE authority;
- coherent batches are preferred over artificial micro-checkpoints;
- Ubuntu/Windows CI belongs at meaningful evidence boundaries;
- target-machine interaction is required only when CI/mocks cannot establish the required fact;
- provider mutation, cleanup, broker switching, autonomous scheduling, PostgreSQL runtime promotion, and LIVE authority are separate gates;
- stacked preparation may never bypass upstream authority;
- zero-promotion/zero-case outcomes are legitimate and must not be weakened to manufacture activity;
- newer local files from a failed run are not automatically accepted state.

Current phase state:

- **Phases 1–22: ACCEPTED / MERGED.**
- Phase23: **VALIDATED / TARGET EVIDENCE COMPLETE / MERGE PENDING** on PR #25.
- Phase23 policy fingerprint: `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`.
- Phase23 validated implementation/repair head before docs closeout: `803d43e43e8931f03ba836a23b781a7c3d3ee687`.

## 4. Non-negotiable data rules

- Preserve exact provider-native ticker text and case.
- Ticker text never proves instrument identity or historical continuity.
- Historical populations are point-in-time/observation-driven; current survivors are not projected backward.
- Current active/delisted state is not retrospective eligibility.
- Ambiguity is quarantined/excluded, never guessed.
- Acquisition/replay must be restartable, checkpointed, deterministic, duplicate-safe, and auditable.
- No synthetic pre-2021 intraday bars from daily history.
- Finalized canonical data outranks provisional live observations.
- Data/model/authority transitions require explicit lineage and independent validation.
- Partial-run analytical files do not establish an accepted operational baseline without the applicable accepted handoff.

Accepted historical boundary:

- Alpaca raw SIP daily controlled extension: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- Pre-2021 1h/4h history remains absent rather than fabricated.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

The cumulative foundation remains frozen at endpoint **2026-08-14**. Later current evidence is an explicit extension/handoff, not a rewrite of that audit.

## 5. ML authority rules

Production ML emits raw `p_down`, `p_neutral`, `p_up`. Argmax is diagnostic only and never standalone trade authority. The accepted production model is immutable until an explicit challenger/acceptance process replaces it.

Accepted production model:

- `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

ML may inform downstream deterministic evaluation but cannot independently choose a trade, broker, order, or authority transition.

## 6. Strategy/research/AI rules

- Regime routing belongs outside strategy implementations.
- Strategies emit deterministic evidence, not opaque conclusions.
- Expensive analogue/Monte Carlo/scenario/options/news work is promoted-candidate only.
- Zero-promotion/no-op states are valid; thresholds are not weakened after results merely to create trades.
- Accepted Phase11 support: **0 SUPPORTED**, 3 MIXED (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`), 5 UNSUPPORTED.
- Only historically SUPPORTED strategies may promote under the accepted Phase11 contract.
- AI is an independent auditor/reviewer. It cannot rewrite accepted evidence, manufacture a trade from a rejected case, create provider/order authority, replace deterministic direction/instrument/geometry/risk authority, or promote LIVE execution.

Phase23 proved that this gate remains active on current evidence: **23 WARM/HOT directional cases were considered on 2026-08-21 and 0 promoted** because the frozen accepted SUPPORTED set is empty.

That is not a reason to weaken the gate. It is evidence that the next analytical improvement must address strategy quality/support through a formal challenger process.

## 7. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase13 risk envelope includes:

- risk at stop <= 0.5% current equity;
- single-name notional <= 10% current equity;
- liquidity/buying-power/account-state checks;
- exposure/concentration/correlation revalidation where applicable.

Geometry, sizing, and portfolio admission remain deterministic authority. AI cannot override them.

## 8. Broker/provider/execution authority architecture

### 8.1 Webull

Primary PAPER/sandbox broker and future LIVE broker only after a separate LIVE-authority phase. Accepted Phase18 evidence proves fresh L1, preview, deterministic sandbox submit, exact reconciliation, exactly-one cancel, exact later `CANCELLED`, zero fill, and flat/zero-open final state.

### 8.2 Alpaca

Manual secondary/fallback. Never automatic failover.

### 8.3 Switching and uncertainty

Broker switching is explicit. Open orders/positions must be reconciled first. Cancel/close/flatten is provider mutation and requires its own applicable authority. Unknown or uncertain mutation state fails closed; there is no blind retry or automatic cross-broker failover.

### 8.4 Webull read operating policy

Normal sustained Webull read traffic targets **80% of the most specific current documented endpoint limit**. Endpoint-specific limits override broader limits. Sustained realtime candidate monitoring should prefer streaming. HTTP 429 reads use cooldown/backoff. Ambiguous mutation responses require reconciliation before any next mutation.

### 8.5 Phase20 orchestration authority

Policy:

`phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls`

Fingerprint:

`b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`

Phase20 may read local artifacts, persist local run state/journals, execute deterministic software-only shadow stages, and retry explicitly retry-safe local work under bounded policy. It cannot initiate provider reads/writes, broker writes, external mutation-stage work, automatic broker switching/failover, LIVE promotion, scheduler/daemon authority, or PostgreSQL runtime promotion. A registered job never creates authority its enclosing phase does not already possess.

Phase23 intentionally remains separate from this registry; current finalized provider-backed acquisition did not silently widen Phase20.

### 8.6 Phase21 unified PAPER submit authority

Policy:

`phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`

Fingerprint:

`0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`

Authority contract:

`phase21-paper-execution-authority-v1-broker-paper-run-scoped`

Accepted rules:

- every **new real PAPER provider submit** crosses one default-deny central seam;
- raw `adapter.submit(plan)` exists exactly once under `packages/`, in `packages/execution/engine.py`;
- Webull PAPER and Alpaca PAPER require exact broker/PAPER/run-scope authority;
- missing, false, malformed, stale, or mismatched authority blocks before submit;
- deterministic existing-order reuse needs no new authority because it performs no new provider mutation;
- SHADOW remains authority-free;
- Phase18 original explicit certification authority remains separate;
- Phase15 PAPER validates authority before live quote/provider initialization;
- browser/control plane cannot acquire Phase21 authority;
- Phase20 external mutation-stage registration remains blocked;
- LIVE and automatic failover remain disabled.

Phase21 final exact head: `174110e3688a0b8c087555a56adafaab99905c66`; final CI `32782618589`; merge `ed9e156437e3924293b90f06620ebbe9534fab15`.

### 8.7 Phase22 routine PAPER operator binding

Policy:

`phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`

Fingerprint:

`1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`

Phase22 locks:

- PAPER/SANDBOX only;
- Webull default/primary;
- Alpaca explicit manual selection only;
- accepted Phase13/14 evidence through Phase15 input resolution only;
- `prepare|execute` operator command surface;
- no arbitrary ticker, quantity, price, geometry, LIVE, or command-line confirmation input;
- exact interactive Phase21 confirmation only when accepted executable cases exist;
- coordination delegates to `Phase15ExecutionRunEngine`;
- no direct broker adapter, quote resolver, order builder, or raw submit seam in Phase22;
- Phase15 immutable outcomes remain authoritative;
- Phase19 consumes outcomes read-only;
- provider uncertainty stops without blind retry/failover and requires reconciliation;
- browser execution, scheduler execution, automatic failover, and LIVE remain disabled.

Cross-platform CI `32787337500`: Ubuntu **974 passed in 13.80s**, Windows **974 passed in 33.93s**, every validator through Phase22 PASS, provider calls/writes/broker writes 0/0/0.

Target-machine `prepare --broker webull` resolved accepted as-of `2026-08-14` with 0 accepted execution cases, required no run authority, and returned `PREPARED_ZERO_PROVIDER_CALLS`.

### 8.8 Phase23 routine current finalized analytical binding

Policy fingerprint:

`00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`

Contract:

- explicit prior finalized `as_of` required;
- provider-free `prepare`;
- exact chronological advancement from the latest **accepted** discovery baseline;
- only `MASSIVE_MARKET_REFERENCE_READS` may be authorized, and only when missing finalized market/reference evidence requires them;
- no broker reads/writes;
- no provider mutations;
- no Massive downstream research/news/options authority under the frozen zero-SUPPORTED gate;
- no Phase14 AI calls under that same zero-path;
- no Phase21 submit authority;
- no Phase22 execution;
- no scheduler/PostgreSQL/browser/LIVE/automatic-failover authority;
- accepted model and historical strategy-support evidence are verified/reused, not silently replaced;
- local analytical writes are allowed and explicitly distinguished from external mutations;
- post-2026-08-14 Phase15 input requires a hash-bound Phase23 current-analysis handoff.

Operational recovery rules added after target evidence:

- Parquet/Pandas null-like `previous_effective_state` values normalize to `None` only for that nullable persisted field;
- partial failed output cannot become an accepted baseline without a valid Phase23 handoff;
- market advancement requires exact requested-session coverage, zero entitlement skips, and all expected raw/canonical/derived partitions;
- feature advancement requires exact checkpoint completion and current source lineage.

Final validated implementation/repair head before documentation closeout:

`803d43e43e8931f03ba836a23b781a7c3d3ee687`

Cross-platform validation:

- push run `32802151860`: Ubuntu/Windows SUCCESS;
- PR run `32802154831`: Ubuntu/Windows SUCCESS;
- **988 passed** on Ubuntu;
- **988 passed** on Windows;
- every validator through Phase23 PASS.

Target finalized cycle for **2026-08-21**:

- accepted baseline retained at 2026-08-14;
- five sessions advanced: Aug 17–21;
- final repaired run required no additional external reads because the previously authorized market/reference data were already local;
- WARM/HOT directional cases considered: **23**;
- promoted candidates: **0**;
- Phase12 research cases: **0**;
- Phase13 cases: **0**;
- Phase14 AI reviews: **0**;
- Phase22-ready execution cases: **0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- independent persisted validation: **PASS**.

Phase23 run scope for the successful repaired target cycle:

`a9f398fcd32e302af125bcf9d81789efadb417da879ff178942880580ab69209`

### 8.9 LIVE

LIVE execution is disabled. PAPER-provider acceptance is not LIVE acceptance. Any future LIVE phase must preregister limits, failure handling, reconciliation, explicit authorization, and negative-path evidence independently.

## 9. Phase ledger

1. **Phase 1 — Foundation:** project/config/session/time foundations.
2. **Phase 2 — Provider ingestion foundation:** restartable acquisition/storage/checkpoints/raw evidence.
3. **Phase 3 — Canonical/session-aware data:** Parquet/DuckDB canonical foundation and replay-safe handling.
4. **Phase 4 — Instrument identity/history:** point-in-time reference evidence, stable identities, ambiguity quarantine.
5. **Phase 5 — Live market state:** Massive delayed/realtime state with freshness/delay/gap semantics.
6. **Phase 6 — Feature engine:** 33 deterministic point-in-time features.
7. **Phase 7 — Universe registry:** point-in-time routing/eligibility without survivor projection.
8. **Phase 8 — Broad discovery:** cheap-first discovery, activity/health routing, persistence/hysteresis.
9. **Phase 9 — Regime engine:** market/sector/ticker hierarchy and prior-only thresholds.
10. **Phase 10 — ML probability/evaluation:** PIT labels/features, walk-forward evaluation, model registry/acceptance.
11. **Historical extension/audit:** controlled Alpaca raw-SIP daily extension to 2016 and cumulative lineage audit.
12. **Phase 11 — Strategy evaluation/regime routing:** deterministic variants, external regime routing, support/promotion policy.
13. **Phase 12 — Deep candidate research:** promoted-only analogue and deterministic empirical scenario/bootstrap research.
14. **Phase 13 — Context/instrument/geometry/portfolio risk:** deterministic plan and portfolio risk.
15. **Phase 14 — Independent AI audit/alerting:** bounded AI review and Engine-vs-AI artifacts.
16. **Phase 15 — Broker-neutral SHADOW/PAPER execution + outcome learning:** Webull primary/Alpaca manual secondary, fresh quote, preflight, reconciliation, risk, deterministic IDs, uncertainty fail-closed, LIVE disabled.
17. **Phase 16 — Browser control plane/production operations:** loopback browser/API, CSRF/same-origin, audit/idempotency, recovery, explicit switch/cleanup planning; browser not execution authority.
18. **Phase 17 — Provider-readonly operational readiness:** accepted Webull sandbox + Alpaca paper reads/reconciliation with mutations disabled; merge `65d5a7b58c6894eba27722465741c92db9a33aaf`.
19. **Phase 18 — Paper Provider Mutation Lifecycle Validation:** accepted/merged `55bdd7446f0bbd4225de264187c7f5fb601991b0`; one-share Webull sandbox lifecycle with explicit authorization, submit once, cancel once, exact `CANCELLED`, zero fill, flat/zero-open.
20. **Phase 19 — Operations Dashboard & Paper/Shadow Observability:** accepted/merged `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`; read-only local operator diagnostics, no provider writes/browser execution/LIVE/failover.
21. **Phase 20 — Deterministic Run Orchestration & Shadow Operations:** accepted/merged `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`; restart-safe local DAG/run engine and provider-free shadow rehearsal; no external mutation/scheduler/PostgreSQL/LIVE authority.
22. **Phase 21 — Unified Paper Execution Authority:** accepted/merged `ed9e156437e3924293b90f06620ebbe9534fab15`; central default-deny PAPER submit authority, exactly one raw submit seam, SHADOW unchanged, LIVE/auto-failover/browser execution disabled.
23. **Phase 22 — Operational Webull-primary PAPER Runner:** accepted/merged `15c0a997ec847764e41fbd525ff52aa8c58f96ac`; routine operator binding over accepted Phase15/21, Webull default, exact interactive run authority for nonzero cases, zero-case no-provider behavior, no new submit seam or authority class.
24. **Phase 23 — Operational Current Analysis Cycle:** validated/target-evidence complete on PR #25; advances explicit finalized sessions through market/reference, canonical/features, discovery/regimes, accepted ML and frozen strategy support, then verifies downstream zero paths and produces a Phase15/22-ready current handoff without broker/PAPER execution.

The historical extension/audit is a non-numbered roadmap item between Phase10 and Phase11; accepted numbered labels remain Phase1 through Phase23.

## 10. Recent acceptance/validation evidence

### Phase19

- accepted merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- final docs-head CI `32739682576`: 932 tests on both OS;
- provider/broker writes 0.

### Phase20

- final exact-head CI `32766072120`: 945 tests on Ubuntu and Windows;
- every validator through Phase20 PASS;
- external mutation-stage registration BLOCKED;
- provider calls/writes/broker writes 0/0/0;
- merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.

### Phase21

- first CI exposed a real Phase18 direct-submit bypass; validator was not weakened;
- final exact head `174110e3688a0b8c087555a56adafaab99905c66`;
- final CI `32782618589` green;
- exactly one raw submit seam;
- provider calls/writes/broker writes 0/0/0;
- merge `ed9e156437e3924293b90f06620ebbe9534fab15`.

### Phase22

- implementation head `68f16256c8f9976ae5b6283dde437e93fbe70155`;
- CI `32787337500`: Ubuntu 974 passed in 13.80s; Windows 974 passed in 33.93s;
- every validator through Phase22 PASS;
- raw submit seam count 1;
- provider calls/writes/broker writes 0/0/0;
- merge `15c0a997ec847764e41fbd525ff52aa8c58f96ac`;
- target-machine zero-case prepare: as-of 2026-08-14, Webull, 0 accepted execution cases, authority required false, `PREPARED_ZERO_PROVIDER_CALLS`.

### Phase23

- first target execute exposed persisted nullable-state `NaN` deserialization; run failed closed;
- repaired without threshold/support/authority changes;
- validated implementation head `803d43e43e8931f03ba836a23b781a7c3d3ee687`;
- push CI `32802151860` green Ubuntu/Windows;
- PR CI `32802154831` green Ubuntu/Windows;
- 988 tests pass on each OS;
- successful finalized target run through 2026-08-21 advanced 5 sessions, considered 23 WARM/HOT directional cases, promoted 0, produced 0 Phase12/13/14/Phase22-ready cases, and recorded 0 broker/order/PAPER/LIVE writes;
- independent persisted validation PASS.

## 11. Performance/stabilization boundary

Post-Phase19 stabilization baseline:

`121503590d3c0b18fa9cc19e4c8210b04e2f8d47`

Retained performance evidence:

- 50,000-row optimized feature batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0.

## 12. Next-phase selection boundary

After Phase23 documentation-head CI is green and PR #25 is merged:

1. verify authoritative `main` contains the accepted current-analysis handoff and target-evidence contract;
2. audit the 2026-08-21 current discovery/regime/ML/current-strategy artifacts and rejection reasons;
3. treat the frozen **0-SUPPORTED Phase11 strategy set** as the principal currently exposed analytical bottleneck unless the merged-code audit identifies a higher-priority correctness issue;
4. define a strategy challenger/support-replacement phase from preregistered historical/current out-of-sample evidence rather than lowering thresholds to manufacture activity;
5. preserve promoted-only expensive research and independent Phase13/14 boundaries;
6. keep Phase21/22 as the only PAPER-submit authority/operator path;
7. GUI work may consume stable current artifacts and implement the approved ATLAS dashboard/settings design, but browser authority remains observational/control-plane only;
8. do not assume scheduler or PostgreSQL promotion is next merely because those are future infrastructure goals;
9. keep LIVE and automatic broker failover disabled.

The likely substantive next analytical target is **strategy challenger / support replacement**, because Phase23 proves the current pipeline itself is functioning and the accepted support gate—not current-data freshness or PAPER plumbing—is what blocks downstream cases.

The exact next numbered phase must still be defined and locked after Phase23 is authoritative on `main`.

## 13. Documentation/security/recovery

Every meaningful acceptance boundary synchronizes README, roadmap, current status, phase flow when stale, active phase spec, PR evidence, and configuration docs as applicable.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. Never commit API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata.

Recovery sequence: inspect `main`, open PRs/branches/latest CI; read `current_status.md`, this roadmap, `phase23_operational_current_analysis_cycle.md`, `phase22_operational_paper_runner.md`, `phase21_unified_paper_execution_authority.md`, and `phase_flow.md`; preserve explicit authority boundaries; continue from the exact current boundary rather than reopening accepted work without new evidence.