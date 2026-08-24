# Phase 20 — Deterministic Run Orchestration & Shadow Operations

**State: ACCEPTED / MERGED — final exact-head cross-platform validation complete.**

## Purpose

Phase 20 fills the explicit `packages/jobs/` orchestration gap after the accepted Phase 1–19 analytical, execution, and observability foundation. It establishes a deterministic, restart-safe, auditable local run engine for shadow-operation rehearsal before any scheduler daemon, PostgreSQL operational-state rollout, or additional provider/execution authority is considered.

This phase is infrastructure, not a trading-authority expansion.

## Accepted baseline

Phase 20 is based on the merged post-Phase19 stabilization boundary:

`121503590d3c0b18fa9cc19e4c8210b04e2f8d47`

The accepted Phase 19 policy/fingerprint remain upstream authority evidence. Phase 18/19 are not reopened.

## Authority lock

Contract:

`phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls`

Policy fingerprint:

`b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`

Phase 20 permits:

- local artifact reads;
- local run-state/journal writes;
- deterministic software-only shadow rehearsal;
- bounded retries only for explicitly retry-safe local stages;
- restart/resume from durable local state.

Phase 20 forbids:

- provider reads initiated by the Phase 20 orchestration path;
- provider writes;
- broker writes;
- external mutation-stage registration;
- blind retry of any external mutation;
- live execution promotion;
- automatic cross-broker failover;
- automatic broker switching;
- AI execution authority;
- implicit scheduler/daemon authority;
- making PostgreSQL a runtime prerequisite;
- guessing through unknown run/stage state.

The accepted Phase 18 paper mutation mechanism remains separate and is not callable merely because Phase 20 can orchestrate jobs.

## Implemented scope

### 20A — deterministic job model

`packages/jobs/` provides:

- `status.py` — explicit run/job states plus strict persisted-state invariants and exact persisted type validation;
- `registry.py` — immutable typed stage definitions, dependency validation, deterministic topological order, duplicate/missing/cycle rejection, authority classification, and canonical pipeline fingerprinting;
- `retry.py` — bounded retry policy limited to retry-safe local work;
- `queue.py` — deterministic ready-work ordering plus permanent duplicate stage/idempotency-key rejection within a run queue;
- `worker.py` — one-stage local execution boundary with sanitized failure records and no hidden retries;
- `orchestrator.py` — deterministic run identity, durable manifest/journal, dependency/failure propagation, resume/idempotency, atomic manifest replacement, and fail-closed single-run lease.

### 20B — operator/validation surface

Implemented:

- provider-free `scripts/run_phase20_orchestrator.py` with plan-only default;
- explicit `--execute-shadow` local-only rehearsal mode;
- active living-document presence check including this Phase 20 specification;
- independent `scripts/validate_phase20.py` contract validation;
- Phase 20 unit coverage for deterministic ordering, graph invalidity, authority denial, retry bounds, failure sanitization, dependency blocking, resume/idempotency, interrupted-state handling, lease collision, queue duplicate protection, strict persisted state types, and semantic manifest conflicts;
- Ubuntu/Windows CI integration.

### 20C — fail-closed hardening retained before acceptance

Independent closeout review found and closed the following malformed-state paths rather than documenting around them:

1. A persisted run may not claim `SUCCEEDED` unless every stage is validly `SUCCEEDED`.
2. A successful stage may not exist above a non-successful dependency.
3. A blocked stage must have a failed/blocked dependency.
4. Persisted attempts may not exceed the registered stage maximum.
5. Persisted stage fields are type-checked exactly rather than coerced.
6. A stage cannot be scheduled twice in the same queue even under different idempotency keys.
7. Stage definitions require immutable tuple dependencies and exact enum/bool/int policy types.
8. Unknown, malformed, semantically conflicting, or interrupted persisted state fails closed.

## Determinism and idempotency rules

1. Pipeline/stage definitions have a canonical fingerprint.
2. Run identity is derived from pipeline fingerprint plus an explicit logical slot/key; wall-clock time does not define identity.
3. A completed stage is never rerun during resume of the same run identity.
4. A failed dependency blocks downstream work deterministically.
5. Tie ordering between simultaneously ready stages is stable and deterministic.
6. Duplicate stage IDs, duplicate queued stages, duplicate idempotency keys, missing dependencies, dependency cycles, unknown states, malformed persisted types, semantic manifest conflicts, and conflicting persisted run identity fail closed.
7. A run lease is fail-closed: a second process cannot silently take over an existing active or unreconciled lease.
8. Arbitrary exception messages or handler payloads are not persisted as public run evidence; failure evidence is sanitized to stable error class/reason codes.

## Retry rules

Retries are orchestration policy, never an implicit worker behavior.

- default maximum attempts: 1;
- a stage must opt into retry and be classified as retry-safe local work;
- retries are bounded to the registered maximum;
- external-read and external-mutation work are outside Phase 20 authority;
- mutation-capable work can never be blind-retried by this phase;
- an interrupted `RUNNING` stage becomes fail-closed uncertain state rather than being blindly re-executed.

## Persistence boundary

Phase 20 uses a small local durable state-store implementation so restart/resume semantics can be proven in CI and on Windows without introducing PostgreSQL deployment as a hidden prerequisite.

The store uses atomic manifest replacement and append-only sanitized journal records. PostgreSQL remains the target operational-state architecture but its implementation/migration is a later separately scoped phase.

## Scheduling boundary

Phase 20 does not install or start a background daemon, Windows service, cron task, or autonomous market schedule. It proves the run engine first. A later phase may bind deterministic run slots to a scheduler only under a separately defined authority/scheduling contract.

## Accepted evidence — 2026-08-24

Implementation head:

`6484f8a2eb5cc7e181544725d578b1206ec412df`

Implementation CI:

`32765179020`

- Ubuntu: **945 passed in 14.67s**;
- Windows: **945 passed in 31.88s**;
- every validator through Phase 20 PASS on both platforms.

Final exact PR head:

`e0f89c9cb362f25cf7c58bfc2c6554a0d687ae62`

Final exact-head CI:

`32766072120`

The CI tested merge ref `fbc9bc0e4512598d7d025d177283a356e2833e73` against accepted baseline `121503590d3c0b18fa9cc19e4c8210b04e2f8d47`.

Final results:

- Ubuntu: **945 passed in 14.69s**;
- Windows: **945 passed in 23.46s**;
- every validator through Phase 20 PASS on both platforms;
- Phase 20 validation pipeline fingerprint: `80ff188249df6fcb9cc86b232d6322fc373a0d3f39b95ecbc3274513df63df00`;
- external mutation-stage registration: BLOCKED;
- persisted semantic conflict: BLOCKED;
- deterministic resume/idempotency: PASS;
- plan-only local state writes: 0;
- provider calls performed: 0;
- provider writes performed: 0;
- broker writes performed: 0;
- dependency lock and secret hygiene: PASS;
- ATLAS Doctor: PASS;
- provider-free feature benchmark: PASS with exact 33-feature parity.

Accepted PR:

- PR #21 — `Phase 20: Deterministic run orchestration and shadow operations`;
- merged 2026-08-24;
- accepted merge: `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.

No target broker/provider run was required because Phase 20 explicitly has no provider-call authority.

## Acceptance decision

All locked Phase 20 exit criteria are satisfied:

- focused Phase 20 tests green;
- independent Phase 20 validator green;
- full regression green;
- Ubuntu + Windows CI green on the exact final PR head;
- provider calls 0;
- provider writes 0;
- broker writes 0;
- deterministic replay/resume evidence satisfied;
- documentation synchronized at acceptance;
- PR #21 accepted and merged.

Phase 20 is therefore **ACCEPTED / MERGED**.

## Exit / next-phase rule

The next numbered work must be separately defined and authority-locked from accepted Phase 20 merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`.

The operational destination remains the end-to-end Webull-primary shadow/paper path. Choose the smallest coherent next increment that materially advances that objective without weakening any accepted safety/authority boundary.

No scheduler daemon, PostgreSQL runtime dependency, real provider execution, automatic broker switching/failover, or live promotion is implied by Phase 20 acceptance. Each requires a later explicit phase decision and corresponding evidence.
