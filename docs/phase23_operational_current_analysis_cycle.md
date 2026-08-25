# Phase 23 — Operational Current Analysis Cycle

**Status: ACCEPTED / MERGED**

Upstream baseline: `dd0d6838d76a15edde0783f471ad7e212453cd94` (post-Phase22 synchronized `main`).

Accepted implementation/repair head: `803d43e43e8931f03ba836a23b781a7c3d3ee687`.

Final pre-merge documentation head: `99425a0fa04d2a4faf0b4477343d11434cebd885`.

Accepted merge: **`2004338624766c42b5f4db2bb0976b2047a5c6b0`** through PR #25.

Phase23 closes the operational gap exposed after accepted Phase22: ATLAS had accepted production primitives for market-data acquisition, canonicalization, features, universe, discovery, regimes, ML probabilities, deterministic strategy routing, promoted research, Phase13 planning/risk, Phase14 AI audit, and Phase22 PAPER execution, but did not have one routine operator path that advances a **new finalized market session** through the analytical chain.

Phase23 creates that current-session analytical binding and stops before PAPER order execution. Phase22 remains the only routine PAPER operator entrypoint.

## 1. Purpose

Provide one deterministic, auditable operator workflow for an explicit finalized `as_of` session:

`finalized Massive data/reference refresh -> canonical lake -> 1d/4h/1h features -> point-in-time universe -> discovery foundation/scoring/state -> market/sector + ticker regimes -> accepted ML probabilities + frozen strategy-support current evaluation -> downstream zero-promotion/no-op verification -> Phase22-ready accepted current lineage`

The cycle preserves legitimate zero-candidate and zero-execution-case outcomes. It never weakens strategy support, discovery thresholds, risk rules, model authority, or AI boundaries merely to create a trade.

## 2. Why this phase exists

Repository audit after Phase22 established that:

- finalized Massive acquisition/materialization already existed through `HistoricalBuildService`;
- point-in-time reference sync already existed through `InstrumentRegistryStore`;
- feature materialization already existed through `HistoricalFeatureMaterializer`;
- universe, discovery, market/sector regime, and ticker-regime builders already existed;
- Phase11–14 had accepted implementations but no routine current-cycle coordinator;
- Phase20 orchestration is intentionally provider-free and **must not** be expanded to provider work;
- Phase22 consumes accepted Phase15 input but cannot create missing upstream current analytical evidence;
- Phase11 historical support evidence is frozen and should be verified/reused rather than expensively recomputed during routine runs;
- Phase15's cumulative foundation is frozen at `2026-08-14`, so later current evidence requires a separate hash-bound extension rather than pretending the original cumulative audit covers future sessions.

## 3. Locked authority boundary — Phase23 v2

### Reachable external activity

Only one external read class exists in Phase23 v2, and only under exact run-scoped authorization when required:

- **`MASSIVE_MARKET_REFERENCE_READS`** — finalized Massive daily/minute aggregate acquisition and point-in-time reference snapshot reads required to advance the requested session.

That is the complete Phase23 external authority.

### Why downstream external scopes are absent

Accepted Phase11 support contains **zero SUPPORTED strategies**. Under the accepted promotion contract, Phase23 cannot produce promoted research candidates. Therefore:

- Phase12 remains a promoted-only no-op;
- Phase13 performs no news/options/portfolio reads;
- Phase14 performs no AI calls;
- Phase22-ready execution cases remain zero.

Dormant external authority is not retained merely for future possibility. A later separately accepted strategy-support replacement may add narrowly required scopes if downstream cases can legitimately exist.

### Forbidden

- provider mutation calls;
- broker account/order/position reads or mutations in Phase23 v2;
- order submit/replace/cancel/close/flatten;
- Phase21 PAPER-submit authority acquisition;
- direct invocation of Phase22 `execute`;
- LIVE execution;
- automatic cross-broker failover;
- browser execution authority;
- autonomous scheduler/daemon execution;
- PostgreSQL runtime promotion;
- arbitrary ticker/quantity/price/geometry injection;
- strategy-support reclassification;
- production-model replacement/retraining;
- weakening discovery/promotion/risk thresholds to manufacture candidates;
- registering provider work inside the accepted Phase20 provider-free registry.

## 4. Operator contract

Prepare:

`python scripts/run_phase23_analysis.py prepare --as-of YYYY-MM-DD [--broker webull|alpaca]`

`prepare` is strictly local/provider-free. It:

- requires an explicit prior finalized exchange session;
- resolves the latest **accepted** discovery baseline, not merely the newest file on disk;
- calculates every missing exchange session that must be advanced chronologically;
- inventories local Massive daily/minute files and reference snapshots;
- computes deterministic run/read scopes;
- performs zero external provider/broker/AI calls;
- emits no broker/order mutation authority.

Execute:

`python scripts/run_phase23_analysis.py execute --as-of YYYY-MM-DD [--broker webull|alpaca]`

If finalized market/reference evidence is missing, `execute` requires exact interactive run-scoped confirmation. There is no command-line confirmation argument. A stale/mismatched preparation or changed run scope fails closed.

If all required market/reference evidence is already local, execution proceeds without acquiring unnecessary external-read authority.

The broker option is retained only as deterministic operator/run context for continuity with the later Phase22 PAPER boundary. **Phase23 performs zero broker reads and zero broker writes.**

## 5. Finalized-session and completion semantics

Phase23 operates on an explicit prior finalized exchange session and does not promote provisional intraday observations into finalized canonical truth.

- Massive finalized daily/minute files remain the accepted post-2021 source path.
- Derived 1h/4h bars/features are built from accepted minute data; no synthetic pre-2021 intraday is introduced.
- Every exchange session between the accepted baseline and requested `as_of` advances chronologically.
- Existing current source evidence is reused idempotently when valid.
- Provider unavailability or entitlement gaps fail closed rather than silently selecting a different date.
- Phase5 streaming/live state remains provisional/freshness evidence only.
- Successful market-data advancement must prove every requested session processed, zero entitlement skips, and expected raw/canonical/derived partitions present.
- Feature checkpoints must finish at the exact requested `as_of` with current source lineage.

## 6. Failed-run recovery contract

A failed or partial Phase23 attempt may write local analytical artifacts before the blocking condition is discovered. Those files do **not** become operational authority merely because they are newer.

The next preparation resolves a post-Phase23 baseline only from a valid accepted Phase23 handoff. If no valid handoff exists, the prior accepted baseline remains authoritative even when later discovery files exist locally.

This rule was exercised by the 2026-08-21 target run: the first authorized attempt downloaded/materialized the missing finalized data but then failed during discovery-state deserialization. The repaired run correctly retained `2026-08-14` as the accepted baseline and re-advanced all five sessions rather than silently adopting partial output.

## 7. Persisted-null normalization repair

The first target execution exposed a real storage-boundary defect:

`previous_effective_state` is nullable in `DiscoveryStateRecord`, but a persisted null read through Parquet/Pandas may be represented as floating `NaN`. Pydantic correctly rejected that `NaN` as an invalid discovery enum.

The repair on head `803d43e43e8931f03ba836a23b781a7c3d3ee687`:

- normalizes only null-like persisted values for the nullable `previous_effective_state` field back to `None` before enum validation;
- preserves bootstrap and discovery-state continuity semantics;
- does not alter NORMAL/WATCH/WARM/HOT thresholds, hysteresis, strategy support, model behavior, promotion rules, risk rules, or execution authority;
- adds regression coverage reproducing the exact Parquet/Pandas null case;
- adds accepted-baseline recovery, provider-session completion, and feature-checkpoint guards.

## 8. Frozen model and strategy support

Phase23 does not rerun the Phase11 historical strategy study during routine cycles.

Accepted support remains frozen until a separately accepted strategy-evaluation/challenger phase replaces it:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Routine current evaluation:

- verifies the accepted historical-study lineage and exact support mapping;
- reuses the accepted study without rerunning it;
- preserves the accepted strategy-registry fingerprint;
- evaluates current discovery/regime/feature/ML conditions;
- permits promotion only from historically SUPPORTED strategies;
- fails closed if a promotion appears while the frozen SUPPORTED set is empty.

The accepted production ML model remains `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; raw `p_down/p_neutral/p_up` remain evidence only.

## 9. Current-result value despite zero promotions

Zero promotions do not make Phase23 an empty run. A successful current cycle materializes:

- point-in-time routed/discovery universe;
- broad discovery population;
- NORMAL/WATCH/WARM/HOT state;
- bullish/bearish/neutral directional evidence;
- setup-family and priority evidence;
- market and ticker regimes;
- accepted ML probability evidence for current WARM/HOT directional candidates;
- deterministic current strategy routes/assessments;
- exact rejection reasons, including the frozen historical-support gate.

This current evidence is the proper basis for a later strategy-challenger/replacement decision and for GUI rendering. Phase23 does not alter the support gate merely to produce downstream research or a trade.

## 10. Downstream zero-path verification

With the frozen Phase23 support state:

1. current candidate materialization must produce zero promotions;
2. Phase12 closes as a zero-candidate no-op and accesses no expensive analogue history;
3. Phase13 closes as a zero-case no-op and initializes no research/portfolio provider path;
4. Phase14 closes as a zero-review no-op and initializes/calls no AI provider;
5. the Phase23 current-analysis handoff binds the resulting Phase14 acceptance;
6. Phase15 may accept the later date only through that exact Phase23 handoff anchored to the frozen cumulative foundation;
7. Phase22 remains separate and receives zero current execution cases unless a future accepted strategy-support state changes the upstream result.

## 11. Current-analysis lineage extension

Phase15's cumulative foundation remains immutable at endpoint `2026-08-14` with fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Phase23 does not rewrite that historical audit. It publishes a separate current-analysis handoff containing the frozen foundation identity, Phase23 policy, explicit current `as_of`, accepted model identity, frozen support mapping, current-stage hashes, current Phase14 acceptance, sessions advanced, external read class actually used, and zero mutation/write counters.

For `as_of > 2026-08-14`, Phase15 requires this handoff. The legacy 2026-08-14 accepted path remains valid without Phase23.

## 12. Local persistence versus external mutation

Phase23 legitimately writes local analytical artifacts while advancing a session. This includes canonical/derived market data, features, universe/discovery/regime artifacts, current candidate evidence, and run manifests.

The handoff explicitly distinguishes those writes from forbidden external mutations:

- `local_analytical_writes_allowed = true`;
- `production_model_writes = 0`;
- `external_provider_mutation_writes = 0`;
- `broker_writes = 0`;
- `order_writes = 0`;
- `paper_submits = 0`;
- `live_writes = 0`;
- automatic failover = false.

## 13. Run-state and evidence model

Phase23 remains separate from Phase20's provider-free stage registry. Each run carries:

- explicit finalized `as_of`;
- selected broker context;
- deterministic run-scope fingerprint;
- chronological sessions-to-advance inventory;
- sanitized append journal;
- source/output lineage hashes;
- archived copies/hashes of current strategy, Phase12, Phase13, Phase14, and Phase23 handoff evidence;
- candidate/research/case/review/Phase22-ready counts;
- provider/broker/order/PAPER/LIVE write counters;
- independent persisted-evidence validation.

## 14. Validation evidence

Repair head:

`803d43e43e8931f03ba836a23b781a7c3d3ee687`

Cross-platform repository validation on that head:

- push workflow run `32802151860`: Ubuntu SUCCESS, Windows SUCCESS;
- PR workflow run `32802154831`: Ubuntu SUCCESS, Windows SUCCESS;
- Ubuntu regression: **988 passed**;
- Windows regression: **988 passed**;
- every validator through Phase23 PASS;
- Phase23 policy fingerprint reproduced exactly: `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`;
- exactly one raw `adapter.submit(plan)` remains under `packages/`, in `packages/execution/engine.py`;
- repository validation performs zero real provider/broker/AI calls and zero broker/order writes.

Final pre-merge documentation-head CI:

- workflow run `32803119880`;
- Ubuntu: **988 passed**;
- Windows: **988 passed in 33.87s**;
- every validator through Phase23 PASS.

Independent Phase23 validation contract:

`phase23-validation-v1-persisted-lineage-zero-downstream-provider-mutation-recompute`

It reopens persisted run evidence, rehashes stage/archive artifacts, validates frozen zero-promotion/downstream paths, resolves the Phase15 extension, and proves mutation counters remain zero without making provider/broker/AI/execution calls.

## 15. Target-machine evidence — 2026-08-21 finalized session

### Initial provider-free prepare

On the target Windows machine, exact head `8df43ce723237a6abde46964f0466a4e147e27fa` prepared from accepted baseline `2026-08-14` for finalized session `2026-08-21`:

- sessions to advance: **5** — Aug 17, 18, 19, 20, 21;
- missing reference snapshots: 5;
- missing Massive daily files: 5;
- missing Massive minute files: 4;
- external read class: `MASSIVE_MARKET_REFERENCE_READS`;
- exact run-scoped read authority required: true;
- broker reads/writes disabled;
- broker/order mutations disabled;
- Phase22 execution separate/not invoked;
- disposition: `PREPARED_ZERO_EXTERNAL_CALLS`.

### First authorized execute and discovered defect

The exact read-scoped confirmation was entered. The run stopped fail-closed on the persisted-null `previous_effective_state=NaN` validation defect. No broker/order retry or failover was authorized or attempted.

The authorized read phase had already populated the missing finalized market/reference data before the local analytical block occurred.

### Repaired provider-free prepare

After pulling repair head `803d43e43e8931f03ba836a23b781a7c3d3ee687`, preparation again resolved the **accepted baseline as 2026-08-14**, not the partial Aug. 21 artifacts, and found:

- sessions to advance: 5;
- missing reference snapshots: **0**;
- missing Massive daily files: **0**;
- missing Massive minute files: **0**;
- external read classes: **NONE**;
- explicit read authority required: **False**;
- run scope: `a9f398fcd32e302af125bcf9d81789efadb417da879ff178942880580ab69209`;
- disposition: `PREPARED_ZERO_EXTERNAL_CALLS`.

### Successful repaired execute

Target command:

`python scripts/run_phase23_analysis.py execute --as-of 2026-08-21 --broker webull`

Result:

- execution status: **COMPLETE**;
- sessions advanced: **5**;
- current WARM/HOT directional cases considered: **23**;
- promoted candidates: **0**;
- Phase12 research cases: **0**;
- Phase13 case files: **0**;
- Phase14 AI reviews: **0**;
- Phase22-ready execution cases: **0**;
- broker reads: **0**;
- broker writes: **0**;
- order writes: **0**;
- PAPER submits: **0**;
- LIVE writes: **0**;
- independent validation pass: **True**;
- overall pass: **True**.

Persisted target evidence:

- `data/derived/operations/phase23/v1/runs/year=2026/date=2026-08-21/broker=webull/manifest.json`;
- `data/derived/operations/phase23/v1/runs/year=2026/date=2026-08-21/broker=webull/independent_validation.json`.

The zero-promotion result is accepted evidence, not a failure. Twenty-three current directional WARM/HOT cases were evaluated, but none could pass the frozen historical-support gate because accepted Phase11 contains zero SUPPORTED strategies.

## 16. Acceptance disposition

Phase23 exit criteria are satisfied:

- routine finalized-session operator path: PASS;
- provider-free preparation: PASS;
- run-scoped market/reference read authority: PASS;
- exact chronological current advancement: PASS;
- persisted-null/recovery failure path: PASS after repair;
- market/session and feature-completion guards: PASS;
- frozen production ML/support reuse: PASS;
- zero-SUPPORTED gate preserved: PASS;
- downstream Phase12/13/14 zero paths: PASS;
- Phase15 post-baseline extension: PASS;
- archived/hash-bound evidence and independent validation: PASS;
- local writes distinguished from external mutations: PASS;
- full Ubuntu/Windows CI: PASS;
- target-machine evidence: PASS;
- provider/broker/order/PAPER/LIVE mutations: **0**;
- PR #25: READY then MERGED;
- authoritative merge: **`2004338624766c42b5f4db2bb0976b2047a5c6b0`**.

## 17. Non-goals retained

Phase23 does not improve or replace the model, redesign strategy rules, promote MIXED strategies, add strategies merely to create signals, add scheduler/PostgreSQL authority, give the browser trading authority, submit/cancel/replace/flatten orders, enable LIVE, enable automatic broker failover, or prove profitability.

## 18. Post-Phase23 selection boundary

Phase23 is authoritative on `main`. The next numbered phase is not yet locked.

The primary analytical bottleneck exposed by accepted current evidence is the frozen Phase11 support state: **0 SUPPORTED strategies**. That gate correctly blocks all expensive downstream research, Phase13/14 cases, and Phase22 execution cases despite 23 current WARM/HOT directional cases on 2026-08-21.

The next step is an authoritative-main audit of the current discovery/regime/ML/current-strategy artifacts and exact rejection reasons. If no higher-priority correctness issue is found, the likely next substantive analytical phase is an evidence-driven **strategy challenger / strategy-support replacement process** using preregistered historical/current out-of-sample evidence. It must not lower existing thresholds merely to create activity.

GUI development may consume the stable Phase23 current-artifact contracts when scheduled, but browser work remains a monitoring/control surface and cannot replace the strategy-evidence bottleneck or acquire execution authority.