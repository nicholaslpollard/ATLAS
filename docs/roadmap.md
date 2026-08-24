# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This document is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but data-integrity, validation, model, strategy, provider, broker, automation, and LIVE authority boundaries change only through an explicit documented and independently validated replacement decision.

For exact continuation read [`current_status.md`](current_status.md). For the latest closeout read [`post_phase22_closeout.md`](post_phase22_closeout.md). For Phase22 read [`phase22_operational_paper_runner.md`](phase22_operational_paper_runner.md). For Phase21 authority read [`phase21_unified_paper_execution_authority.md`](phase21_unified_paper_execution_authority.md). For development cadence read [`phase_flow.md`](phase_flow.md).

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, identity, features, and regimes;
3. discover candidates cheaply before expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject the deterministic case to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade LIVE only under separately accepted authority;
10. learn descriptively from outcomes without silently changing model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority;
12. orchestrate restart-safe runs without silently creating provider, broker, scheduler, database-runtime, or LIVE authority;
13. reach routine current end-to-end operation before lower-value infrastructure work displaces that objective.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute/provider roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; current scaffold is not an accepted runtime prerequisite.
- **Massive**: primary broad-market/reference-data provider path.
- **Webull**: primary PAPER/sandbox execution broker; future LIVE only under a separate explicit phase/authority.
- **Alpaca**: manually selectable secondary/fallback; never automatic failover.

### 2.1 Strategic anti-drift anchor

The roadmap destination is the **operational end-to-end ATLAS system**, not any individual infrastructure phase. ATLAS must progress from broad-market discovery through point-in-time evidence, deterministic research/risk planning, and independent AI audit into safe **Webull-primary SHADOW/PAPER execution**, exact reconciliation, observability, and outcome learning before any separately authorized LIVE transition.

Infrastructure, storage, orchestration, scheduling, and control-plane work are justified only when they materially improve correctness, safety, evidence quality, recoverability, performance, or operability of that system. A technically interesting but lower-value infrastructure task must not displace the current end-to-end paper/shadow objective by silent drift.

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
- zero-promotion/zero-case outcomes are legitimate and must not be weakened to manufacture activity.

Current phase state:

- **Phases 1–22: ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Phase21 merge: `ed9e156437e3924293b90f06620ebbe9534fab15`.
- Phase22 merge: `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.
- Current work is the unnumbered `maintenance/post-phase22-closeout` documentation synchronization. It creates no new authority.
- **Phase23 is not yet defined.** It must be selected only after the post-closeout merged-code audit.

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

Accepted historical boundary:

- Alpaca raw SIP daily controlled extension: **2016-01-04 through 2021-08-13**.
- Massive authority: **2021-08-16 onward**.
- Pre-2021 1h/4h history remains absent rather than fabricated.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

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
- Accepted Phase11 support: 0 SUPPORTED, 3 MIXED (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`), 5 UNSUPPORTED.
- AI is an independent auditor/reviewer. It cannot rewrite accepted evidence, manufacture a trade from a rejected case, create provider-order authority, replace deterministic direction/instrument/geometry/risk authority, or promote LIVE execution.

The accepted 2026-08-14 lineage therefore legitimately produces zero downstream execution cases.

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
- Phase18 original explicit certification authority remains separate and required first;
- both Phase18 submission paths compose with narrow Phase21 compatibility scopes rather than bypassing the central seam;
- Phase15 PAPER validates authority before live quote resolver/provider initialization;
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
- accepted Phase13/14 evidence through the existing Phase15 input boundary only;
- `prepare|execute` operator command surface;
- no arbitrary ticker, quantity, price, geometry, LIVE, or command-line confirmation input;
- exact interactive Phase21 confirmation only when accepted executable cases exist;
- coordination delegates to `Phase15ExecutionRunEngine`;
- no direct broker adapter, quote resolver, order builder, or raw submit seam in Phase22;
- Phase15 immutable outcomes remain authoritative;
- Phase19 continues to consume those outcomes read-only;
- provider uncertainty stops without blind retry/failover and requires reconciliation;
- browser execution, scheduler execution, automatic failover, and LIVE remain disabled.

Cross-platform CI `32787337500`: Ubuntu **974 passed in 13.80s**, Windows **974 passed in 33.93s**, every validator through Phase22 PASS, provider calls/writes/broker writes 0/0/0.

Target-machine `prepare --broker webull` resolved accepted as-of `2026-08-14` with 0 accepted execution cases, required no run authority, and returned `PREPARED_ZERO_PROVIDER_CALLS`. This is the correct accepted zero-case behavior and must not be bypassed by fabricating a case.

### 8.8 LIVE

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
20. **Phase 19 — Operations Dashboard & Paper/Shadow Observability:** accepted/merged `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`; read-only local operator diagnostics, no provider writes/browser execution/live/failover.
21. **Phase 20 — Deterministic Run Orchestration & Shadow Operations:** accepted/merged `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`; restart-safe local DAG/run engine and provider-free shadow rehearsal; no external mutation/scheduler/PostgreSQL/LIVE authority.
22. **Phase 21 — Unified Paper Execution Authority:** accepted/merged `ed9e156437e3924293b90f06620ebbe9534fab15`; central default-deny PAPER submit authority, exactly one raw submit seam, SHADOW unchanged, LIVE/auto-failover/browser execution disabled.
23. **Phase 22 — Operational Webull-primary PAPER Runner:** accepted/merged `15c0a997ec847764e41fbd525ff52aa8c58f96ac`; routine operator binding over accepted Phase15/21, Webull default, exact interactive run authority for nonzero cases, zero-case no-provider behavior, no new submit seam or authority class.

The numbering above includes the historical extension/audit as a non-numbered roadmap item between Phase10 and Phase11; the accepted numbered phase labels remain Phase1 through Phase22 as recorded in code/docs/PRs.

## 10. Recent acceptance evidence

### Phase19

- accepted merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- final docs-head CI `32739682576`: 932 tests on both OS;
- provider/broker writes 0.

### Phase20

- final exact-head CI `32766072120`: 945 tests on Ubuntu and Windows;
- every validator through Phase20 PASS;
- external mutation-stage registration BLOCKED;
- persisted semantic conflict BLOCKED;
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
- exact policy fingerprint reproduced;
- raw submit seam count 1;
- provider calls/writes/broker writes 0/0/0;
- merge `15c0a997ec847764e41fbd525ff52aa8c58f96ac`;
- target-machine zero-case prepare: as-of 2026-08-14, Webull, 0 accepted execution cases, authority required false, `PREPARED_ZERO_PROVIDER_CALLS`.

## 11. Performance/stabilization boundary

Post-Phase19 stabilization baseline:

`121503590d3c0b18fa9cc19e4c8210b04e2f8d47`

Retained performance evidence:

- 50,000-row optimized feature batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0.

## 12. Next-phase selection boundary

No Phase23 scope is locked yet.

After the post-Phase22 documentation closeout is CI-green and merged:

1. audit the actual merged operator paths that advance current market/reference data through canonical/features/discovery/regimes/ML/strategy/research/risk/AI artifacts;
2. determine whether the smallest remaining gap is a current end-to-end analytical run binding, a data-freshness/acceptance binding, or another directly evidenced operational defect;
3. prefer reuse of accepted stage implementations and artifacts over rebuilding parallel paths;
4. explicitly preregister any provider-read/write authority needed by that phase;
5. keep broker mutations behind Phase21/22 rather than putting them inside Phase20 orchestration;
6. preserve valid zero-case outcomes rather than tuning to manufacture trades;
7. do not assume scheduler or PostgreSQL promotion is next merely because those remain future infrastructure goals;
8. keep LIVE and automatic broker failover disabled.

A likely strategic target is the missing bridge between the accepted 2026-08-14 analytical artifacts and a routine **current** analytical production run that can naturally feed Phase22, but this is not a locked Phase23 definition until the merged-code audit proves it.

## 13. Documentation/security/recovery

Every meaningful acceptance boundary synchronizes README, roadmap, current status, phase flow when stale, active phase spec, PR evidence, and configuration docs as applicable.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. Never commit API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata.

Recovery sequence: inspect `main`, open PRs/branches/latest CI; read `current_status.md`, this roadmap, `post_phase22_closeout.md`, `phase22_operational_paper_runner.md`, `phase21_unified_paper_execution_authority.md`, and `phase_flow.md`; preserve explicit authority boundaries; continue from the exact current boundary rather than reopening accepted work without new evidence.