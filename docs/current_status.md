# ATLAS Current Status and Handoff

**Living operational handoff. Last synchronized: 2026-08-24.**

This file is the fastest recovery point for a future ATLAS development session.

## 1. Source-of-truth order

When sources disagree, use:

1. accepted code/artifacts on `main` for completed work;
2. active PR branch code and its current CI for in-progress work;
3. active phase living specification;
4. `docs/roadmap.md` for architecture/authority rules;
5. this file for exact current state/evidence/continuation;
6. `docs/phase_flow.md` for phase progression/cadence;
7. `docs/post_phase19_stabilization.md` for the completed post-Phase19 closure/performance audit;
8. root `README.md`;
9. merged PRs for deeper historical evidence;
10. old phase/fix READMEs as provenance only.

## 2. Closed baseline and active phase

Repository: `nicholaslpollard/ATLAS`

Accepted baseline:

- **Phases 1–19 accepted/merged.**
- Phase 18 merge: `55bdd7446f0bbd4225de264187c7f5fb601991b0`.
- Phase 19 merge / accepted baseline: `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`.
- Phase 19 policy fingerprint: `ecd30046a7a3258013a29f0a2982de133f3a4f801aee4ad5e24f79b6bd3b4c3d`.
- Final Phase 19 docs-head CI `32739682576`: Ubuntu 932 passed in 13.78s; Windows 932 passed in 25.80s; every validator through Phase 19 PASS.
- Post-Phase19 stabilization baseline: `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.
- Post-Phase19 stabilization CI `32754626468`: Ubuntu 932 passed in 15.59s; Windows 932 passed in 25.38s; every validator through Phase 19 PASS.
- Post-Phase19 stabilization/performance housekeeping: **COMPLETE**.

Active work:

- **Phase 20 — Deterministic Run Orchestration & Shadow Operations: ACCEPTANCE CANDIDATE.**
- Branch: `phase-20-deterministic-run-orchestration-shadow-operations`.
- PR: **#21**.
- Phase 20 policy: `phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls`.
- Phase 20 policy fingerprint: `b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`.
- Tested implementation head: `6484f8a2eb5cc7e181544725d578b1206ec412df`.
- Implementation-head CI `32765179020`: Ubuntu **945 passed in 14.67s**; Windows **945 passed in 31.88s**; every validator through Phase 20 PASS.
- Provider calls performed by Phase 20 validation: **0**.
- Provider writes: **0**.
- Broker writes: **0**.
- Live execution: **DISABLED**.
- Automatic cross-broker failover: **DISABLED**.

Phase 20 is not yet recorded as accepted/merged. Documentation closeout and final docs-head CI precede PR merge.

## 3. Mandatory phase flow

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

Batch-first is preferred. Authority/external checkpoints override batching. Provider mutation, destructive cleanup, broker switching, autonomous scheduling, PostgreSQL runtime promotion, and future live authority may never be inferred from credentials/configuration/prior acceptance.

## 4. Architecture snapshot

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probabilities -> deterministic strategy routing/evaluation -> promotion -> analogue/Monte Carlo/scenarios -> news/events -> instrument/geometry -> portfolio risk -> deterministic case -> independent AI audit -> alerts -> paper/shadow/live execution -> outcome learning -> browser control plane`

Storage/provider roles:

- Parquet: durable analytical/history lake.
- DuckDB: analytical engine.
- PostgreSQL: target operational state; current repository SQL scaffold remains nonoperational and is not a Phase 20 prerequisite.
- Massive: primary broad-market/reference provider.
- Webull: primary planned execution broker; downstream realtime L1 execution evidence where entitled.
- Alpaca: manually selectable secondary/fallback; never automatic failover.

## 5. Non-negotiable architecture/authority rules

- Preserve exact provider-native ticker text/case.
- Ticker text never proves identity continuity.
- Historical populations remain point-in-time.
- Ambiguity is quarantined/excluded, never guessed.
- No synthetic pre-2021 intraday from daily data.
- Finalized canonical facts outrank provisional live observations.
- ML emits probability evidence; argmax is diagnostic only.
- Accepted production model cannot be silently replaced by a challenger.
- AI is independent audit only and cannot create execution authority.
- LONG geometry: `stop < entry < target`.
- SHORT geometry: `stop > entry > target`.
- Unknown broker/provider/run state fails closed.
- Uncertain writes are never retried blindly.
- Automatic cross-broker failover is forbidden.
- Paper/sandbox authority does not imply live authority.
- Phase 20 orchestration cannot create provider/broker/scheduler authority by registering a job.

## 6. Accepted data/model evidence

Historical provider boundary:

- Alpaca raw SIP daily controlled authority: 2016-01-04 through 2021-08-13.
- Massive authority: 2021-08-16 onward.
- No synthetic pre-2021 1h/4h history.

Accepted cumulative data/lineage fingerprint:

`6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6`

Accepted production ML:

- ID `mlmodel-hgb15-2026-08-14-d485e6c287bacce1`;
- `hgb_leaf15_iter100`;
- 33 point-in-time predictors;
- outputs `p_down/p_neutral/p_up`;
- protected holdout 2026-05-12 through 2026-08-11;
- 63 sessions / 454,773 rows;
- log loss 0.948693;
- Brier 0.560422;
- macro OVR AUC 0.570016;
- exact replay.

Phase 11 strategy support: SUPPORTED 0; MIXED 3 (`momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`); UNSUPPORTED 5. Zero supported strategies correctly produced zero accepted promotions on the locked case.

## 7. Accepted execution/control-plane evidence

### Phase 15

Broker-neutral shadow/paper execution includes fresh quote, provider preflight, reconciliation, current risk revalidation, protective geometry, deterministic client-order IDs/idempotency, uncertainty fail-closed, same-ticker add/flip disabled, live hard-disabled, Webull primary and Alpaca manual secondary.

### Phase 16

Accepted loopback-first browser control plane includes CSRF/same-origin, audit/idempotency, restart recovery, explicit broker switching/cleanup planning, and no independent browser execution authority.

### Phase 17

Accepted real-provider read-only readiness established working Webull sandbox and Alpaca paper account/order/position reads and reconciliation with provider writes 0.

### Phase 18

Policy `phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live`, fingerprint `9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7`.

Accepted Webull sandbox lifecycle:

`fresh L1 -> explicit paper authorization -> pre-reconcile flat -> preview -> submit once -> exact reconcile -> cancel once -> bounded read-only reconciliation -> exact CANCELLED -> zero fill -> flat/zero-open`

Immediate post-cancel read uncertainty was handled fail-closed without repeat cancel, flatten, retry, or failover. Later independent Order Detail and Order History both proved `CANCELLED`.

Normal sustained Webull read traffic is locked to **80% of the most specific current documented endpoint limit**; endpoint-specific limits outrank broader limits. No automatic failover.

### Phase 19

Accepted read-only local operations/observability layer:

- dedicated `apps/web/phase19.html` shell;
- GET-only `/api/v1/observability`;
- local sanitized candidate, AI-audit, outcome, lineage, and persisted live-market diagnostics;
- optional 5/15/30-second observability refresh, default OFF;
- accepted Phase 16 explicit read-only broker refresh remains separate;
- Phase 19 observability initializes no broker adapter or market-data client;
- Phase 19 provider reads/writes 0;
- no browser execution authority;
- no live promotion or automatic failover.

## 8. Phase 20 implementation evidence

Phase 20 fills the prior empty `packages/jobs/` orchestration boundary with a provider-free deterministic local run engine.

Implemented substrate:

- strict explicit run/stage status model;
- immutable typed stage registry and deterministic DAG/topological ordering;
- canonical pipeline fingerprint and deterministic run ID from pipeline fingerprint + explicit logical slot;
- bounded retry policy for explicitly retry-safe local stages only;
- deterministic ready queue with duplicate stage/idempotency protection;
- local worker with sanitized error evidence and no hidden retries;
- atomic local manifest replacement and append-only sanitized journal;
- fail-closed single-run lease;
- restart/resume that never reruns completed stages;
- interrupted `RUNNING` state fails closed instead of blind re-execution;
- semantic persisted-manifest validation, including false-success/dependency/attempt conflicts;
- provider-free plan-only runner and explicit local shadow rehearsal;
- independent Phase 20 validator and cross-platform unit/regression coverage.

Implementation-head CI `32765179020` proved on both Ubuntu and Windows:

- policy contract/fingerprint exact;
- validation pipeline fingerprint `80ff188249df6fcb9cc86b232d6322fc373a0d3f39b95ecbc3274513df63df00`;
- external mutation-stage registration BLOCKED;
- persisted semantic conflict BLOCKED;
- deterministic resume/idempotency PASS;
- plan-only local state writes 0;
- provider calls/writes 0;
- broker writes 0;
- dependency lock, secret hygiene, ATLAS Doctor and feature self-test PASS;
- full suite 945/945 on each OS.

No target broker/provider run is required for Phase 20 because the phase has no provider-call authority.

## 9. Performance/housekeeping baseline

The completed stabilization audit is recorded in `docs/post_phase19_stabilization.md`.

Accepted target feature performance:

- 50,000 rows / 7,454 symbols / 7 sessions;
- optimized batch ~4.00265s / 12,491.74 rows/s;
- prior pandas baseline ~594.58s / 84.09 rows/s;
- ~148.5x batch speedup;
- all 33 features exact parity, max difference 0.0;
- provider/broker calls/writes 0.

Data-I/O housekeeping already retained:

- normalizer and bar builder use DuckDB `COPY ... RETURN_STATS` to avoid redundant post-write count scans;
- materializer reuses validated staging `checked_rows` after byte-for-byte canonical promotion;
- staging move/hardlink semantics remain deferred until recovery behavior is proven;
- derived-row-count caching on no-op materialization was reviewed and deferred because it would alter manifest shape without measured bottleneck evidence;
- generated `webull_data_sdk.log*` is ignored as local runtime output.

## 10. Current broker and automation authority

### Webull

Primary planned execution broker. Sandbox reads, fresh L1 execution-evidence path, and Phase 18 sandbox mutation lifecycle are accepted. Live authority is **not** granted.

### Alpaca

Manual secondary/fallback. Paper reads accepted. No automatic failover.

### Phase 20 orchestration

Local-only. It cannot perform provider reads/writes, broker writes, automatic broker switching, or autonomous scheduling. The accepted Phase 18 paper mutation mechanism remains separate and is not callable merely because Phase 20 can execute a stage graph.

### Live

Live execution disabled. Any live-money transition requires a separately defined phase and separate explicit authorization.

## 11. Exact continuation point

Do **not** reopen accepted Phase 18/19 work or repeat provider mutation merely to reconfirm it.

Current closeout sequence:

1. synchronize `docs/phase20_run_orchestration.md`, this handoff, `docs/roadmap.md`, root `README.md`, and PR #21 against implementation-head evidence `6484f8a2eb5cc7e181544725d578b1206ec412df` / CI `32765179020`;
2. run the final docs-head Phase 20 Ubuntu + Windows CI boundary;
3. require every validator through Phase 20 and the full regression suite green on both platforms;
4. mark PR #21 ready/accepted and merge it;
5. verify the merge on `main` and synchronize final accepted merge/CI evidence;
6. only then define and authority-lock the next numbered phase.

Until a later explicit phase changes authority, live execution stays disabled, broker switching stays explicit/manual, automatic failover stays forbidden, and autonomous scheduling/PostgreSQL runtime promotion remain out of scope.

## 12. Configuration/security status

Tracked `.env.example` is non-secret and may contain public/default endpoints plus blank secret placeholders.

Never commit or expose API secrets, passwords, security codes, raw broker account IDs, tokens, or signed request metadata. Commented secrets are still secrets.

## 13. Future-session startup

A future session should inspect `main`, branches/open PRs/latest CI, then read this file, `docs/roadmap.md`, the active phase specification, `docs/phase_flow.md`, and `docs/post_phase19_stabilization.md`. Preserve explicit provider/live/automation authority boundaries and continue from section 11 rather than reopening accepted work without new evidence.
