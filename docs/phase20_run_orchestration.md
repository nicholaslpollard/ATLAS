# Phase 20 — Deterministic Run Orchestration & Shadow Operations

**State: ACTIVE — DEFINE/LOCK complete; implementation in progress.**

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

## Scope

### 20A — deterministic job model

Implement the currently empty `packages/jobs/` foundation:

- `status.py` — explicit run/job states and terminal-state rules;
- `registry.py` — immutable stage definitions, dependency validation, deterministic topological order, duplicate/missing/cycle rejection, authority classification;
- `retry.py` — bounded retry policy limited to retry-safe local work;
- `queue.py` — deterministic ready-work ordering and duplicate idempotency-key rejection;
- `worker.py` — one-stage execution boundary with sanitized failure records and no hidden retries;
- `orchestrator.py` — deterministic run identity, durable manifest/journal, dependency/failure propagation, resume/idempotency, and fail-closed single-run lease.

### 20B — operator/validation surface

- provider-free Phase 20 runner with plan-only default;
- explicit local shadow-rehearsal mode;
- independent `validate_phase20.py` contract validation;
- unit tests for deterministic ordering, cycles, dependencies, retries, resume, idempotency, lease collision, and authority denial;
- CI integration on Ubuntu and Windows.

### 20C — acceptance

Require:

- focused Phase 20 tests green;
- independent Phase 20 validator green;
- full regression green;
- Ubuntu + Windows CI green;
- provider calls 0;
- provider writes 0;
- broker writes 0;
- deterministic replay/resume evidence;
- documentation synchronized.

No target broker/provider run is required because Phase 20 explicitly has no provider-call authority.

## Determinism and idempotency rules

1. Pipeline/stage definitions have a canonical fingerprint.
2. Run identity is derived from pipeline fingerprint plus an explicit logical slot/key; wall-clock time does not define identity.
3. A completed stage is never rerun during resume of the same run identity.
4. A failed dependency blocks downstream work deterministically.
5. Tie ordering between simultaneously ready stages is stable and deterministic.
6. Duplicate stage IDs, duplicate idempotency keys, missing dependencies, dependency cycles, unknown states, and conflicting persisted run identity fail closed.
7. A run lease is fail-closed: a second process cannot silently take over an existing active lease.
8. Arbitrary exception messages or handler payloads are not persisted as public run evidence; failure evidence is sanitized to stable error class/reason codes.

## Retry rules

Retries are orchestration policy, never an implicit worker behavior.

- default maximum attempts: 1;
- a stage must opt into retry and be classified as retry-safe local work;
- retries are bounded;
- external-read and external-mutation work are outside Phase 20 authority;
- mutation-capable work can never be blind-retried by this phase.

## Persistence boundary

Phase 20 uses a small local durable state-store implementation so restart/resume semantics can be proven in CI and on Windows without introducing PostgreSQL deployment as a hidden prerequisite.

The store must use atomic manifest replacement and append-only sanitized journal records. PostgreSQL remains the target operational-state architecture but its implementation/migration is a later separately scoped phase.

## Scheduling boundary

Phase 20 does not install or start a background daemon, Windows service, cron task, or autonomous market schedule. It proves the run engine first. A later phase may bind deterministic run slots to a scheduler after orchestration semantics are accepted.

## Exit criteria

Phase 20 may be accepted only when the deterministic local orchestration substrate is independently validated, cross-platform green, fully documented, and still shows zero provider/broker calls or writes. Any request to add real provider execution, automatic broker switching/failover, live promotion, or autonomous scheduling requires a new explicit authority boundary rather than being folded into Phase 20.
