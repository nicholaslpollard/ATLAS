# Phase 23 — Operational Current Analysis Cycle

**Status: ACTIVE / IMPLEMENTATION + VALIDATION IN PROGRESS**

Upstream baseline: `dd0d6838d76a15edde0783f471ad7e212453cd94` (post-Phase22 synchronized `main`).

Phase23 closes the smallest operational gap exposed after accepted Phase22: ATLAS has accepted production primitives for market-data acquisition, canonicalization, features, universe, discovery, regimes, ML probabilities, deterministic strategy routing, promoted research, Phase13 planning/risk, Phase14 AI audit, and Phase22 PAPER execution, but there is no one routine operator path that advances a **new finalized market session** through the analytical chain.

Phase23 creates that current-session analytical binding. It stops before PAPER order execution. Phase22 remains the only routine PAPER operator entrypoint.

## 1. Purpose

Provide one deterministic, auditable operator workflow for an explicit finalized `as_of` session:

`finalized Massive data/reference refresh -> canonical lake -> 1d/4h/1h features -> point-in-time universe -> discovery foundation/scoring/state -> market/sector + ticker regimes -> accepted ML probabilities + frozen strategy-support current evaluation -> downstream zero-promotion/no-op verification -> Phase22-ready accepted current lineage`

The cycle must preserve legitimate zero-candidate and zero-execution-case outcomes. It must never weaken strategy support, discovery thresholds, risk rules, or AI boundaries merely to create a trade.

## 2. Why this phase is required

Repository audit after Phase22 found:

- finalized Massive acquisition/materialization exists through `HistoricalBuildService`;
- point-in-time reference sync exists through `InstrumentRegistryStore`;
- feature materialization exists through `HistoricalFeatureMaterializer`;
- universe, discovery, market/sector regime, and ticker-regime builders already exist;
- Phase11–14 each have accepted implementations, but there is no routine current-cycle coordinator;
- Phase20 orchestration is intentionally provider-free and **must not** be expanded to provider work;
- Phase22 faithfully consumes accepted Phase15 input but cannot create missing upstream current analytical evidence;
- the Phase11 closeout recomputes the expensive historical support study, even though its accepted support decision is frozen and should be verified/reused during routine operation;
- Phase15 was originally pinned to the cumulative-foundation endpoint `2026-08-14`, so a separately hash-bound current-analysis extension is needed for later accepted Phase14 dates rather than pretending the original cumulative audit covered future sessions.

## 3. Locked authority boundary — Phase23 v2

### Reachable external activity

Only one external read class is authorized in Phase23 v2, and only when explicitly authorized for the exact run scope:

1. **`MASSIVE_MARKET_REFERENCE_READS`** — finalized Massive daily/minute aggregate acquisition and point-in-time reference snapshot reads required to advance the requested session.

That is the complete Phase23 v2 external authority.

### Why downstream read scopes are intentionally absent

The accepted Phase11 support state contains **zero SUPPORTED strategies**. Under the accepted promotion contract, this deterministically means Phase23 v2 cannot produce promoted research candidates. Therefore:

- Phase12 must remain a promoted-only no-op;
- Phase13 performs no news/options/portfolio reads;
- Phase14 performs no AI calls;
- Phase22-ready execution cases remain zero.

Granting Massive research, broker-portfolio, or AI-call authority while those paths are unreachable would be dormant authority with no operational purpose. Phase23 therefore does **not** authorize those scopes. A later separately accepted strategy-support replacement may introduce the additional read authorities when downstream cases can actually exist.

### Forbidden

- provider mutation calls;
- broker account/order/position mutation;
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
- model retraining or accepted production-model replacement;
- weakening discovery/promotion/risk thresholds to manufacture candidates;
- registering provider-read work inside the accepted Phase20 provider-free registry.

## 4. Operator contract

Phase23 exposes one routine CLI with two modes:

`python scripts/run_phase23_analysis.py prepare --as-of YYYY-MM-DD [--broker webull|alpaca]`

`prepare` is strictly local/provider-free. It must:

- require an explicit prior finalized exchange session rather than silently choosing an incomplete current day;
- identify the prior local discovery-state baseline;
- calculate every missing exchange session that must be advanced in order;
- inventory local Massive daily/minute files and reference snapshots;
- compute the deterministic run fingerprint and exact required read class;
- perform **zero external provider/broker/AI calls**;
- emit no broker/order mutation authority.

`python scripts/run_phase23_analysis.py execute --as-of YYYY-MM-DD [--broker webull|alpaca]`

If finalized market/reference evidence is missing, `execute` requires exact interactive run-scoped confirmation. There is no command-line confirmation argument. A stale/mismatched preparation or changed run scope fails closed.

If all required market/reference evidence is already local, execution may proceed without acquiring unnecessary external-read authority.

The broker option is retained as deterministic operator/run context for continuity with the later Phase22 PAPER boundary. **Phase23 v2 performs zero broker reads and zero broker writes.**

## 5. Finalized-session semantics

Phase23 operates on an explicit prior finalized exchange session. It must not use provisional intraday observations as finalized canonical facts.

- Daily and minute Massive flat-file sources remain the accepted post-2021 finalized source path.
- Canonical daily/minute materialization remains existing Phase2/3 implementation authority.
- Derived 1h/4h bars/features are built only from accepted minute data; no synthetic pre-2021 intraday is introduced.
- Missing sessions between the current local baseline and requested `as_of` are advanced chronologically; the cycle may not skip an intermediate finalized exchange session.
- Existing history is reused/idempotently skipped when its source/manifest lineage remains current.
- Provider unavailability or entitlement gaps fail closed rather than silently selecting a different date.
- Phase5 live/streaming state remains provisional/freshness evidence and is not promoted into finalized analytical truth by Phase23.

## 6. Frozen model and strategy support

Phase23 does not rerun the Phase11 historical strategy study during routine cycles.

The accepted Phase11 strategy-support result remains frozen until a separately accepted strategy-evaluation phase changes it:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Routine current evaluation must:

- verify the accepted historical-study lineage and exact support mapping;
- reuse that accepted support evidence without rerunning the historical study;
- preserve the accepted strategy-registry fingerprint;
- evaluate current discovery/regime/feature/ML conditions;
- preserve the rule that only historically `SUPPORTED` strategies can promote candidates;
- fail closed if a promotion appears while the frozen SUPPORTED set is empty.

The accepted production ML model remains `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`; raw `p_down/p_neutral/p_up` remain evidence only.

## 7. Current-result value despite zero promotions

Zero promotions do **not** make Phase23 an empty run. A successful current cycle still materializes current evidence that can be inspected directly or later rendered by the ATLAS GUI:

- point-in-time routed/discovery universe;
- broad discovery population;
- NORMAL/WATCH/WARM/HOT state;
- bullish/bearish/neutral directional evidence;
- setup-family evidence and priority distributions;
- market regime;
- ticker regime/risk state;
- accepted ML probability evidence for current WARM/HOT directional candidates;
- current deterministic strategy routes/assessments;
- exact rejection reasons, including the frozen historical-support gate.

This current evidence is the intended basis for the next strategy-development/challenger decision. Phase23 must not alter the support gate merely to produce downstream research or a trade.

## 8. Downstream zero-path verification

For the frozen Phase23 v2 support state:

1. current candidate materialization must produce zero promotions;
2. Phase12 must close as a zero-candidate no-op and must not access expensive analogue history;
3. Phase13 must close as a zero-case no-op and initialize no Massive research provider or portfolio snapshot read;
4. Phase14 must close as a zero-review no-op and initialize/call no AI provider;
5. the Phase23 current-analysis handoff must bind the resulting Phase14 acceptance;
6. Phase15 input resolution may accept the later date only through that exact Phase23 handoff anchored to the frozen cumulative foundation;
7. Phase22 remains separate and receives zero current execution cases unless a future accepted strategy-support state changes the upstream result.

## 9. Current-analysis lineage extension

Phase15's accepted cumulative foundation remains immutable at its original endpoint, `2026-08-14`.

Phase23 does **not** rewrite or claim to extend that historical audit. Instead it publishes a separate current-analysis handoff containing:

- frozen cumulative-foundation fingerprint and endpoint;
- Phase23 policy fingerprint;
- explicit current `as_of`;
- accepted production-model identity;
- frozen strategy-support mapping;
- current-stage artifact hashes;
- current Phase14 acceptance hash;
- sessions advanced;
- external read class actually used;
- zero production-model/provider-mutation/broker/order/PAPER/LIVE writes.

For `as_of > 2026-08-14`, Phase15 input resolution requires this handoff before accepting current Phase14 evidence. The legacy 2026-08-14 accepted path remains valid without Phase23.

## 10. Local persistence versus external mutation

Phase23 necessarily writes local analytical artifacts while advancing the current session. This includes canonical/derived market data, features, universe/discovery/regime artifacts, current candidate evidence, and run manifests.

Those local analytical writes are expected and explicitly distinguished from forbidden authority-changing or external mutations.

Phase23 handoff evidence therefore records:

- `local_analytical_writes_allowed = true`;
- `production_model_writes = 0`;
- `external_provider_mutation_writes = 0`;
- `broker_writes = 0`;
- `order_writes = 0`;
- `paper_submits = 0`;
- `live_writes = 0`;
- automatic failover = false.

## 11. Run-state and evidence model

Phase23 remains separate from Phase20's provider-free stage registry. It may reuse generic deterministic hashing/atomic-write patterns but does not alter Phase20 authority.

Each Phase23 run has:

- explicit finalized `as_of`;
- selected broker context;
- deterministic run-scope fingerprint;
- chronological sessions-to-advance inventory;
- sanitized append journal;
- source/output lineage hashes;
- archived copies/hashes of current strategy, Phase12, Phase13, Phase14, and Phase23 handoff evidence;
- final candidate/research/case/review/Phase22-ready counts;
- explicit provider/broker/order/PAPER/LIVE write counts.

No uncertain provider mutation semantics are introduced because Phase23 performs no provider mutation.

## 12. Validation requirements

Independent validation must prove at minimum:

- deterministic Phase23 policy fingerprint;
- Webull default and Alpaca manual context only;
- external authority contains only `MASSIVE_MARKET_REFERENCE_READS`;
- explicit finalized `as_of` is required;
- provider-free `prepare` initializes no provider/broker/AI client;
- external-read challenge is deterministic and run-scoped;
- no command-line confirmation argument;
- no arbitrary ticker/quantity/entry/stop/target input;
- no provider/broker/order mutation calls in Phase23;
- Phase21/22 execution authority is not acquired/invoked by the Phase23 coordinator;
- exactly one raw `adapter.submit(plan)` remains under `packages/`, in the accepted execution engine;
- Phase20 provider-free authority remains unchanged;
- accepted Phase11 support mapping is exact and historical study is not rerun;
- accepted production-model identity remains exact;
- zero-promotion path skips Phase12 expensive history, Phase13 provider/portfolio reads, and Phase14 AI calls;
- current strategy and current-analysis handoffs are hash-bound and fail closed on tampering;
- local analytical persistence is not mislabeled as an external mutation;
- production-model/provider-mutation/broker/order/PAPER/LIVE writes remain zero.

CI/fakes must perform zero real provider/broker/AI calls.

## 13. Target-machine boundary

After the exact implementation head passes full Ubuntu/Windows CI:

1. run `prepare` on the target machine for an explicit prior finalized session; this remains provider-free;
2. inspect its deterministic session/missing-file/read-authority plan;
3. if Massive market/reference reads are required, type the exact run-scoped authorization only for that prepared scope;
4. execute one current analytical cycle;
5. record data/reference advancement, current discovery/regime/candidate evidence, lineage hashes, and final zero/nonzero counts;
6. under the current frozen support map, zero promotions are expected and accepted;
7. do **not** invoke Phase22 PAPER execution merely to create acceptance evidence.

## 14. Non-goals

Phase23 does not:

- improve or replace the production model;
- redesign strategy rules or support thresholds;
- promote MIXED strategies to SUPPORTED;
- introduce new strategies merely to create signals;
- perform Massive research/news/options calls;
- read broker portfolio/account/order state;
- call the Phase14 AI provider;
- add autonomous scheduling;
- promote PostgreSQL;
- give the browser trading authority;
- submit/cancel/replace/flatten orders;
- enable LIVE;
- enable automatic broker failover;
- prove profitability.

## 15. Exit criteria

Phase23 may be ACCEPTED only when:

- one routine current-cycle operator path advances every required finalized session through existing accepted analytical implementations;
- provider-free preparation is independently proven;
- exact Massive market/reference read authority is default-deny and run-scoped;
- current data/reference/features/universe/discovery/regimes advance deterministically;
- accepted ML/strategy support is reused without historical restudy;
- the frozen zero-SUPPORTED gate remains intact;
- downstream Phase12/13/14 zero paths are independently validated with zero external downstream calls;
- the Phase15 post-baseline lineage extension is hash-bound to the frozen cumulative foundation and current Phase14 evidence;
- run evidence is archived/hash-bound;
- local analytical writes are accurately distinguished from forbidden external mutations;
- full Ubuntu/Windows CI is green;
- required target-machine read-only evidence is recorded;
- living documentation is synchronized;
- no provider mutation, broker/order/PAPER/LIVE mutation occurred.

After Phase23, ATLAS will have its first accepted routine **current-market analytical cycle**. The resulting current evidence should then drive the separately authorized strategy-challenger work and provide the real data surface needed for subsequent GUI development.