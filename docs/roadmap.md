# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but data-integrity, validation, and trading-authority boundaries change only through an explicit documented and independently validated replacement decision.

For exact continuation read [`current_status.md`](current_status.md). For current Phase21 evidence read [`phase21_unified_paper_execution_authority.md`](phase21_unified_paper_execution_authority.md). For the development sequence read [`phase_flow.md`](phase_flow.md).

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
9. alert, shadow, paper-trade, and eventually trade live only under explicit authority;
10. learn descriptively from outcomes without silently changing accepted model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority;
12. orchestrate deterministic restart-safe runs without silently creating provider, broker, scheduler, or live authority.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute/provider roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; current scaffold is not an accepted runtime prerequisite.
- **Massive**: primary accepted broad-market/reference-data provider path.
- **Webull**: primary paper/sandbox execution broker; future live only under a separate explicit phase/authority.
- **Alpaca**: manually selectable secondary/fallback; never automatic failover.

### 2.1 Strategic anti-drift anchor

The roadmap destination is the **operational end-to-end ATLAS system**, not any individual infrastructure phase. ATLAS must progress from broad-market discovery through point-in-time evidence, deterministic research/risk planning, and independent AI audit into safe **Webull-primary SHADOW/PAPER execution**, exact reconciliation, observability, and outcome learning before any separately authorized live transition.

Infrastructure, storage, orchestration, scheduling, and control-plane work are justified only when they materially improve correctness, safety, evidence quality, recoverability, performance, or operability of that system. At every phase boundary, audit both implementation and proposed next work against this roadmap. A technically interesting but lower-value infrastructure task must not displace the agreed paper/shadow objective by silent drift.

## 3. Mandatory phase execution contract

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Principles:

- code existence or passing tests alone is not acceptance;
- credentials/configuration/connectivity never silently expand provider/live authority;
- coherent batches are preferred over artificial micro-checkpoints;
- Ubuntu/Windows CI belongs at meaningful evidence boundaries;
- target-machine interaction is required only when CI/mocks cannot establish required evidence;
- provider mutation, cleanup, broker switching, autonomous scheduling, PostgreSQL runtime promotion, and LIVE authority are separate gates;
- stacked preparation may never bypass upstream authority.

Current phase state:

- **Phases 1–20: ACCEPTED / MERGED.**
- Phase18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase19 merge: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase20 merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.
- Post-Phase20 anti-drift baseline used for Phase21: `4afe8e0a5238b176edd47eb6e70359ccff6d65b1`.
- **Phase21: VALIDATED / MERGE PENDING.** Validated implementation head `d3599f3a184142de4ac5f03b58fc355f0bb11001`; CI `32781962354`: Ubuntu 964 / Windows 964; every validator through Phase21 PASS.

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
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact deterministic replay.

## 6. Strategy/research/AI rules

- Regime routing belongs outside strategy implementations.
- Strategies emit deterministic evidence, not opaque conclusions.
- Expensive analogue/Monte Carlo/scenario/options/news work is promoted-candidate only.
- Zero-promotion/no-op states are valid; thresholds are not weakened to manufacture trades.
- Phase11 support: 0 SUPPORTED, 3 MIXED, 5 UNSUPPORTED among eight variants.
- AI is an independent auditor/reviewer. It cannot rewrite accepted evidence, manufacture a trade from a rejected case, create provider-order authority, replace deterministic direction/instrument/geometry/risk authority, or promote LIVE execution.

## 7. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase13 risk envelope used downstream includes:

- risk at stop <= 0.5% current equity;
- single-name notional <= 10% current equity;
- liquidity/buying-power/account-state checks;
- exposure/concentration/correlation revalidation where applicable.

## 8. Broker/provider/execution authority architecture

### 8.1 Webull

Primary planned broker for PAPER/sandbox and, only after a future separate LIVE-authority phase, controlled live execution. Accepted Phase18 evidence proves fresh L1, preview, deterministic sandbox submit, exact reconciliation, exactly-one cancel, exact later `CANCELLED`, zero fill, and flat/zero-open final state.

### 8.2 Alpaca

Manual secondary/fallback. Never automatic failover.

### 8.3 Switching and uncertainty

Broker switching is explicit. Open orders/positions must be reconciled first. Cancel/close/flatten is provider mutation and requires its own applicable authority. Unknown or uncertain mutation state fails closed; there is no blind retry or automatic cross-broker failover.

### 8.4 Webull read operating policy

Normal sustained Webull read traffic targets **80% of the most specific current documented endpoint limit**. Endpoint-specific limits override broader limits. Sustained realtime candidate monitoring should prefer streaming. HTTP 429 reads use cooldown/backoff. Ambiguous mutation responses require reconciliation before any next mutation.

### 8.5 Phase20 orchestration authority

Contract:

`phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls`

Fingerprint:

`b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`

Phase20 may read local artifacts, persist local run state/journals, execute deterministic software-only shadow stages, and retry explicitly retry-safe local work under bounded policy. It cannot initiate provider reads/writes, broker writes, external mutation-stage work, automatic broker switching/failover, LIVE promotion, scheduler/daemon authority, or PostgreSQL runtime promotion. A registered job never creates authority its enclosing phase does not already possess.

### 8.6 Phase21 unified PAPER submit authority

Policy:

`phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`

Validated fingerprint:

`0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`

Authority contract:

`phase21-paper-execution-authority-v1-broker-paper-run-scoped`

Phase21 locks these rules:

- every **new real PAPER provider submit** crosses one default-deny central seam;
- raw `adapter.submit(plan)` exists exactly once under `packages/`, in `packages/execution/engine.py`;
- Webull PAPER and Alpaca PAPER require exact broker/PAPER/run-scope authority;
- missing, false, malformed, stale, or mismatched authority blocks before submit;
- deterministic existing-order reuse needs no new authority because it performs no new provider mutation;
- SHADOW remains authority-free;
- Phase18 original explicit certification authority remains separate and required first;
- Phase18 standard and operational-validation paths compose with narrow Phase21 compatibility scopes rather than bypassing the central seam;
- Phase15 PAPER validates authority before live quote resolver initialization;
- browser/control plane cannot acquire Phase21 authority;
- Phase20 external mutation-stage registration remains blocked;
- LIVE and automatic failover remain disabled.

See `docs/phase21_unified_paper_execution_authority.md`.

### 8.7 LIVE

LIVE execution is disabled. PAPER-provider acceptance is not LIVE acceptance. A future LIVE phase must preregister limits, failure handling, reconciliation, and explicit authorization independently.

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
18. **Phase 17 — Provider-readonly operational readiness:** accepted Webull sandbox + Alpaca paper reads/reconciliation with mutations disabled. Merge `65d5a7b58c6894eba27722465741c92db9a33aaf`.
19. **Phase 18 — Paper Provider Mutation Lifecycle Validation:** accepted/merged `55bdd7446f0bbd4225de264187c7f5fb601991b0`; one-share Webull sandbox lifecycle with explicit authorization, submit once, cancel once, exact `CANCELLED`, zero fill, flat/zero-open. Fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
20. **Phase 19 — Operations Dashboard & Paper/Shadow Observability:** accepted/merged `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`; read-only local operator diagnostics, no provider writes/browser execution/live/failover. Fingerprint `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
21. **Phase 20 — Deterministic Run Orchestration & Shadow Operations:** accepted/merged `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`; deterministic local DAG/run engine, restart/resume, bounded local retry, provider-free shadow rehearsal; no external mutation/scheduler/PostgreSQL/LIVE authority.
22. **Phase 21 — Unified Paper Execution Authority & Operational Binding:** validated/merge pending; central default-deny PAPER submit authority, deterministic run/intent/plan scopes, Phase15 and both Phase18 bindings, exactly one raw submit seam, SHADOW unchanged, LIVE/auto failover/browser execution disabled. Validated head `d3599f3a184142de4ac5f03b58fc355f0bb11001`, CI `32781962354` 964/964 on Ubuntu and Windows.

## 10. Recent accepted/validated evidence

### Phase19

- accepted merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- final docs-head CI `32739682576`: 932/932 on both OS;
- provider/broker writes 0.

### Phase20

- implementation CI `32765179020`: Ubuntu 945 / Windows 945;
- final exact-head CI `32766072120`: Ubuntu 945 / Windows 945;
- every validator through Phase20 PASS;
- external mutation-stage registration BLOCKED;
- persisted semantic conflict BLOCKED;
- provider calls/writes/broker writes 0/0/0;
- accepted merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.

### Phase21 implementation boundary

- first validator run exposed a real direct-submit bypass in `phase18_operational_validation.py`; validator was not weakened;
- validated implementation head `d3599f3a184142de4ac5f03b58fc355f0bb11001`;
- CI `32781962354`: Ubuntu **964 passed in 15.42s**, Windows **964 passed in 24.52s**;
- every validator through Phase21 PASS;
- exactly one raw submit seam;
- provider calls/writes/broker writes 0/0/0.

## 11. Performance/stabilization boundary

Post-Phase19 stabilization baseline:

`121503590d3c0b18fa9cc19e4c8210b04e2f8d47`

Retained performance:

- 50,000-row optimized feature batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0.

## 12. Current acceptance / next-phase boundary

Phase21 implementation is validated but not yet accepted/merged. Final living-document synchronization and exact docs-head cross-platform CI remain inside the Phase21 acceptance boundary.

After Phase21 acceptance/merge:

1. audit the merged end-to-end path from accepted Phase13/14 evidence through Phase15 PAPER challenge/authority, Webull execution/reconciliation, Phase19 observability, and outcomes;
2. identify the smallest missing operator/run binding needed for routine end-to-end PAPER operation;
3. reuse accepted runners/adapters/artifacts rather than rebuilding them;
4. explicitly lock any provider-read/write, cleanup, scheduling, or persistence authority required by the next increment;
5. do not assume scheduler or PostgreSQL work is next merely because it remains available;
6. keep LIVE and automatic broker failover disabled.

No additional real provider mutation is required merely to close Phase21; Phase18 already supplies accepted target mutation evidence and Phase21 changes the internal authority seam.

## 13. Documentation/security/recovery

Every meaningful acceptance boundary synchronizes README, roadmap, current status, phase flow when stale, active phase spec, PR evidence, and configuration docs as applicable.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. Never commit API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata.

Recovery sequence: inspect `main`, open PRs/branches/latest CI; read `current_status.md`, this roadmap, active phase spec, and `phase_flow.md`; preserve explicit authority boundaries; continue from the exact current phase rather than reopening accepted work without new evidence.
