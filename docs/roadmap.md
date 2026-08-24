# ATLAS Master Roadmap

**Living architecture, phase, and authority document. Last synchronized: 2026-08-24.**

ATLAS is the **Autonomous Trading, Learning, and Analysis System**. This file is the long-term architecture and authority lock. Implementation may evolve when measured evidence requires it, but changes must preserve the data-integrity, validation, and trading-authority boundaries below unless an explicit replacement decision is documented and independently validated.

For exact operational continuation, read [`current_status.md`](current_status.md). For the active Phase 20 contract/evidence, read [`phase20_run_orchestration.md`](phase20_run_orchestration.md). For the mandatory development sequence, read [`phase_flow.md`](phase_flow.md). Post-Phase19 housekeeping is in [`post_phase19_stabilization.md`](post_phase19_stabilization.md). Phase 19 evidence is in [`phase19_operations_observability.md`](phase19_operations_observability.md). Phase 18 provider-mutation evidence is in [`phase18_operational_validation.md`](phase18_operational_validation.md).

## 1. Mission

Build a broad-market system that can:

1. observe a large U.S. market universe;
2. maintain point-in-time-safe market/reference data, instrument identity, features, and regimes;
3. discover candidates cheaply before expensive research;
4. estimate outcome probabilities with conventional ML;
5. route candidates to deterministic strategies appropriate to context/regime;
6. promote only evidence-supported candidates into deeper analogue/scenario/options/news analysis;
7. produce deterministic entry/stop/target/horizon/risk plans;
8. subject the deterministic case to an independent AI audit;
9. alert, shadow, paper-trade, and eventually trade live only under explicit authority;
10. learn descriptively from outcomes without silently changing accepted model/strategy authority;
11. expose operational state through a browser control plane without making the browser an execution authority;
12. orchestrate deterministic restart-safe local runs without silently creating provider, broker, scheduler, or live authority.

## 2. Architecture lock

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability surface -> deterministic strategy routing/evaluation -> candidate promotion -> analogue/Monte Carlo/scenario research -> news/events/sentiment -> instrument/geometry -> portfolio risk -> consolidated deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/compute roles:

- **Parquet**: durable analytical/history lake.
- **DuckDB**: analytical/query engine.
- **PostgreSQL**: target persistent operational state; current SQL/database scaffold is not accepted operational implementation and is not a Phase 20 runtime prerequisite.
- **Massive**: primary accepted broad-market/reference-data provider path.
- **Webull**: primary planned execution broker; accepted downstream realtime L1 execution-evidence source where locally entitled.
- **Alpaca**: manually selectable secondary/fallback execution broker; never automatic failover.

### 2.1 Strategic anti-drift anchor

The roadmap destination is the **operational end-to-end ATLAS system**, not any individual infrastructure phase. ATLAS must progress from broad-market discovery through point-in-time evidence, deterministic strategy/research/risk planning and independent AI audit into safe **Webull-primary shadow/paper execution**, exact reconciliation, observability, and outcome learning before any separately authorized live transition is considered.

Infrastructure, storage, orchestration, scheduling, and control-plane work are justified only when they materially improve correctness, safety, evidence quality, recoverability, performance, or operability of that agreed system. At every phase boundary, the implementation and proposed next increment must be independently audited against this roadmap and the current authority lock. Work that does not materially advance the agreed end-to-end paper/shadow objective should not displace higher-value operational work merely because it is technically available. Any genuine change to the destination or architecture requires an explicit documented replacement decision and independent validation; it may never arise through silent drift.

## 3. Mandatory phase execution contract

ATLAS advances by explicit numbered phases under `docs/phase_flow.md`:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Required principles:

- code existence or passing tests alone is never acceptance;
- credentials/configuration/connectivity never silently expand provider/live authority;
- use coherent batches rather than artificial micro-checkpoints;
- full regression and Windows/Ubuntu CI belong at meaningful evidence boundaries;
- target-machine interaction is required only where CI/mocks cannot establish the evidence;
- explicit provider mutation, cleanup, broker switching, autonomous scheduling, PostgreSQL runtime promotion, and future live authority remain separate gates;
- stacked preparation may occur only under `docs/phase_flow.md` and never bypass upstream authority.

Current phase state:

- **Phases 1–19: ACCEPTED / MERGED.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge / accepted baseline: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Final Phase 19 docs-head CI `32739682576`: Ubuntu 932 passed in 13.78s; Windows 932 passed in 25.80s; every validator through Phase 19 PASS.
- Post-Phase19 stabilization baseline: `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.
- **Phase 20: ACCEPTANCE CANDIDATE on PR #21; implementation independently validated, documentation/final CI/merge pending.**
- Phase 20 tested implementation head: `6484f8a2eb5cc7e181544725d578b1206ec412df`.
- Phase 20 implementation CI `32765179020`: Ubuntu 945 passed in 14.67s; Windows 945 passed in 31.88s; every validator through Phase 20 PASS.

## 4. Non-negotiable data rules

- Preserve exact provider-native ticker text and case.
- Ticker text alone never proves instrument identity or historical continuity.
- Historical populations are point-in-time/observation-driven; current survivors are not projected backward.
- Current active/delisted state is not retrospective historical eligibility.
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

Production ML emits raw three-class probabilities `p_down`, `p_neutral`, and `p_up`. Argmax is diagnostic only and is never a standalone trade signal. Accepted production model authority is immutable until an explicit challenger/acceptance process replaces it.

Accepted production model:

- ID `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- HGB `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- deterministic replay exact.

## 6. Strategy/research rules

- Regime routing belongs in scanner/router orchestration, not inside strategies.
- Strategies emit deterministic case evidence, not opaque conclusions.
- Expensive analogue/Monte Carlo/scenario/options/news work is promoted-candidate only.
- No-op/zero-promotion states are valid; thresholds are never weakened merely to create trades.
- Accepted Phase 11 support: 0 SUPPORTED, 3 MIXED, 5 UNSUPPORTED among eight tested variants.

## 7. AI authority rules

AI is an independent auditor/reviewer. It may approve, caution, or reject a deterministic case and identify risks, but it cannot rewrite accepted evidence, manufacture a trade from a rejected case, create provider-order authority, silently replace deterministic direction/instrument/geometry/risk authority, or promote live execution.

## 8. Geometry and portfolio-risk rules

Mandatory geometry:

- LONG: `stop < entry < target`;
- SHORT: `stop > entry > target`.

Accepted Phase 13 risk envelope used by Phase 18 includes:

- risk at stop <= 0.5% current equity;
- single-name notional <= 10% current equity;
- liquidity/buying-power/account-state checks;
- exposure/concentration/correlation revalidation where applicable.

## 9. Broker, provider, and orchestration architecture

### 9.1 Webull

Primary planned broker for paper/sandbox and, only after a future separate live-authority phase, controlled live execution. Accepted Phase 18 evidence proves fresh L1, preview, deterministic sandbox submit, exact client-order reconciliation, exactly-one cancel, exact later `CANCELLED`, zero fill, and flat/zero-open reconciliation.

### 9.2 Alpaca

Manually selectable secondary/fallback. It is not an automatic failover destination.

### 9.3 Switching

Broker switching is explicit only. ATLAS must inspect/reconcile open orders and positions first. Any cancel/close/flatten required to make a broker safe is itself a provider mutation and requires corresponding explicit authority. Unknown state fails closed.

### 9.4 Provider rate-limit operating policy

Locked 2026-08-24 policy:

- normal sustained Webull **read** traffic targets **80% of the most specific current documented endpoint limit**;
- endpoint-specific limits override broader/global limits;
- 90% is not the normal sustained target;
- any higher temporary read burst must be explicitly bounded, read-only, and below hard provider limits;
- trading mutations are governed by ATLAS risk/reconciliation/idempotency, not provider maximum write rates;
- sustained realtime candidate monitoring should prefer Webull MQTT/streaming rather than high-rate HTTP polling;
- HTTP 429 read handling uses cooldown/backoff;
- ambiguous mutation responses require reconciliation before any further mutation;
- no automatic cross-broker failover.

### 9.5 Phase 20 orchestration authority

Phase 20 is a local deterministic orchestration substrate only. Its contract is:

`phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls`

Policy fingerprint:

`b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`

It may read local artifacts, persist local run state/journals, execute deterministic software-only shadow stages, and retry explicitly retry-safe local work within bounded policy. It may not initiate provider reads, provider writes, broker writes, external mutation-stage work, automatic broker switching/failover, live promotion, AI execution authority, scheduler/daemon authority, or PostgreSQL runtime promotion.

A registered job never creates authority that its enclosing phase does not already possess.

### 9.6 Live

Live execution is disabled. Paper-provider acceptance is not live acceptance. A future live phase must preregister limits, observation, failure handling, and explicit authorization independently.

## 10. Phase ledger

1. **Phase 1 — Foundation:** project/config/session/time foundations, canonical timezone, basic validation.
2. **Phase 2 — Provider ingestion foundation:** restartable acquisition, storage contracts, checkpoints, raw evidence.
3. **Phase 3 — Canonical/session-aware data:** Parquet/DuckDB canonical foundation, exchange/session semantics, duplicate/replay-safe handling.
4. **Phase 4 — Instrument identity/history:** point-in-time reference evidence, stable identifiers where authoritative, ambiguity quarantine.
5. **Phase 5 — Live market state:** Massive delayed/realtime WebSocket state, freshness/delay/gap semantics, provisional snapshot/journal behavior.
6. **Phase 6 — Feature engine:** 33 deterministic point-in-time features with deterministic batch/incremental behavior.
7. **Phase 7 — Universe registry:** point-in-time routing/eligibility without survivor projection or guessed identity.
8. **Phase 8 — Broad discovery:** cheap-first discovery, activity/health routing, persistence/hysteresis.
9. **Phase 9 — Regime engine:** market/sector/ticker hierarchy, prior-only thresholds, persistence, no guessed sector crosswalk.
10. **Phase 10 — ML probability/evaluation:** point-in-time training/labels/features, walk-forward evaluation, model registry/acceptance, raw probability surface.
11. **Historical extension/audit:** controlled Alpaca raw-SIP daily extension to 2016, provider seam validation, cumulative lineage audit; no synthetic pre-2021 intraday.
12. **Phase 11 — Strategy evaluation/regime routing:** deterministic variants, external regime routing, support classification, promotion policy.
13. **Phase 12 — Deep candidate research:** promoted-only historical analogue and deterministic empirical scenario/bootstrap research.
14. **Phase 13 — Context/instrument/geometry/portfolio risk:** deterministic instrument choice, geometry, sizing, liquidity, exposure/concentration/correlation/risk planning.
15. **Phase 14 — Independent AI audit/alerting:** structured bounded AI review and Engine-vs-AI alert artifacts.
16. **Phase 15 — Broker-neutral shadow/paper execution + outcome learning:** Webull primary/Alpaca manual secondary, fresh quote, preflight, reconciliation, current risk, protective geometry, deterministic IDs, uncertainty fail-closed, descriptive outcomes, live disabled.
17. **Phase 16 — Browser control plane/production operations:** loopback browser/API, CSRF/same-origin, audit/idempotency, recovery, explicit broker switch/cleanup planning; browser is not execution authority.
18. **Phase 17 — Provider-readonly operational readiness:** accepted real Webull sandbox + Alpaca paper reads/reconciliation with provider mutation disabled. Merge `65d5a7b58c6894eba27722465741c92db9a33aaf`.
19. **Phase 18 — Paper Provider Mutation Lifecycle Validation:** accepted/merged at `55bdd7446f0bbd4225de264187c7f5fb601991b0`; exact one-share Webull sandbox lifecycle with explicit authorization, submit once, cancel once, exact `CANCELLED`, zero fill, flat/zero-open. Policy fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.
20. **Phase 19 — Operations Dashboard & Paper/Shadow Observability:** accepted/merged at `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`; read-only local operator dashboard, GET-only observability, persisted candidate/AI/outcome/live-market diagnostics, no Phase 19 provider reads/writes, no browser execution authority, no live promotion or auto failover. Policy fingerprint `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
21. **Phase 20 — Deterministic Run Orchestration & Shadow Operations:** acceptance candidate on PR #21; local-only deterministic DAG/run engine, immutable stage definitions, canonical pipeline/run identity, bounded local retry, atomic manifest/journal persistence, fail-closed leases/resume, strict semantic persisted-state validation, provider-free plan/shadow runner, and independent cross-platform validation. No provider calls/writes, broker writes, autonomous scheduling, PostgreSQL runtime requirement, or live authority.

Phase 19 final evidence:

- clean implementation CI `32738366242`: Ubuntu 932 / Windows 932;
- final docs-head CI `32739682576`: Ubuntu 932 passed in 13.78s / Windows 932 passed in 25.80s;
- every validator through Phase 19 PASS;
- dependency lock, secret hygiene, ATLAS Doctor, browser JS, feature self-test PASS;
- exact 33-feature parity max difference 0.0;
- provider/broker writes 0.

Phase 20 implementation-head evidence:

- tested implementation head `6484f8a2eb5cc7e181544725d578b1206ec412df`;
- CI `32765179020`: Ubuntu **945 passed in 14.67s** / Windows **945 passed in 31.88s**;
- every validator through Phase 20 PASS;
- validation pipeline fingerprint `80ff188249df6fcb9cc86b232d6322fc373a0d3f39b95ecbc3274513df63df00`;
- external mutation-stage registration BLOCKED;
- persisted semantic conflict BLOCKED;
- deterministic resume/idempotency PASS;
- provider calls/writes 0;
- broker writes 0;
- final docs-head CI and merge still required for acceptance.

## 11. Post-Phase19 stabilization boundary

The unnumbered audit in `docs/post_phase19_stabilization.md` closed housekeeping after Phase 19 and became the accepted baseline for Phase 20:

`121503590d3c0b18fa9cc19e4c8210b04e2f8d47`

Accepted performance state retained:

- 50,000-row optimized feature batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x speedup;
- all 33 features exact parity, max difference 0.0;
- normalizer/bar builder use `COPY ... RETURN_STATS` to avoid redundant post-write count scans;
- materializer reuses validated staging row count for byte-for-byte canonical promotion.

A derived-row-count cache for no-op materialization reruns was reviewed and deferred because it would alter persisted manifest shape without measured evidence that the existing metadata-oriented skip scans are material. Staging move/hardlink semantics also remain deferred until recovery behavior is proven.

## 12. Current acceptance / next-phase boundary

Phase 20 authority is locked and its implementation-head evidence is green, but Phase 20 is not accepted until documentation synchronization, final docs-head cross-platform CI, and PR #21 merge are complete.

Closeout sequence:

1. synchronize living Phase 20/current-status/roadmap/root README and PR evidence;
2. require final docs-head Ubuntu + Windows CI green with every validator through Phase 20;
3. mark PR #21 ready/accepted and merge it;
4. verify the accepted `main` merge and synchronize final merge/CI evidence;
5. only then define and authority-lock the next numbered phase, selecting the smallest coherent increment that materially advances the end-to-end operational paper/shadow path toward real Webull-primary paper trading while preserving all existing data, risk, AI, broker, and mutation authority boundaries.

No additional real provider mutation is required for Phase 20. No autonomous scheduler, PostgreSQL runtime promotion, real provider execution, automatic broker switching/failover, or live execution authority may be inferred from Phase 20 acceptance. Those capabilities may be introduced only when a later phase explicitly defines and locks the required authority because they are necessary to advance the operational ATLAS system.

## 13. Batch-first development protocol

Normal coherent work package:

`implementation + targeted tests + validator + CLI/orchestration + documentation/status`

Use the largest safe coherent batch, independent validators and full regression at meaningful evidence boundaries, target-machine interaction only when necessary, and fail closed on identity/data/geometry/broker/mutation/run-state ambiguity.

## 14. Documentation and security policy

Every meaningful boundary synchronizes, as applicable:

- root `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- `docs/phase_flow.md` when process changes;
- active phase spec;
- active PR evidence;
- configuration templates/docs.

Tracked `.env.example` may contain public/default endpoints and blank secret placeholders. It must never contain API secrets, passwords, security codes, raw broker account IDs, or tokens. Commented secrets are still secrets.

## 15. Recovery protocol

A new session should:

1. inspect `main`, open PRs/branches, and latest CI;
2. read `docs/current_status.md`;
3. read this roadmap;
4. read the active phase spec, if any;
5. read `docs/phase_flow.md`;
6. read `docs/post_phase19_stabilization.md` for the prior stabilization baseline;
7. preserve explicit provider/live/automation authority boundaries;
8. continue from the exact phase state rather than reopening accepted work without new evidence.
