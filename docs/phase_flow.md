# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-23.**

This document defines how ATLAS work moves from one numbered phase to the next. It exists to prevent scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc development that bypasses the roadmap **without turning the phase process into unnecessary micro-checkpoints**.

## 1. Core rule

ATLAS advances by explicit numbered phases.

A phase is not complete merely because code exists or tests pass. A phase must move through the complete flow below before the next numbered phase becomes active:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a **control framework, not a requirement to stop after each arrow**. When a whole phase is sufficiently defined, dependencies are available, and authority does not require an intermediate user/external checkpoint, ATLAS should implement the entire phase as one coherent batch and then perform the strongest required validation at the phase evidence boundary.

No credential, endpoint, connected account, implementation detail, prior phase success, or passing CI silently expands provider or live-trading authority.

## 2. Phase states

Every active phase uses one of these states:

- **PLANNED** — purpose and rough place in the roadmap are known, but implementation has not started.
- **ACTIVE** — scope/authority are locked and implementation/evidence work is underway.
- **WAITING_EXTERNAL** — implementation is ready but acceptance requires an external condition such as market hours, provider access, target-machine evidence, or explicit user authorization.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **ACCEPTED** — all phase acceptance criteria and required evidence are satisfied.
- **MERGED** — accepted phase is merged to `main`; its branch may then be removed.

A subphase may be used when a phase contains a genuine authority or external-condition boundary. Subphases do not become independent roadmap phases unless explicitly promoted to a numbered phase.

## 3. Required phase definition

Before implementation begins, the active phase must state:

1. phase number and name;
2. purpose;
3. accepted upstream phase/commit/artifact binding;
4. exact scope;
5. explicit non-goals;
6. authority boundary;
7. data/model/provider dependencies;
8. implementation deliverables;
9. validation/acceptance criteria;
10. target-machine or external evidence requirements, if any;
11. failure/uncertainty behavior;
12. documentation that must be synchronized at acceptance.

Authority-changing phases must additionally preregister the exact authorization checkpoint and fail-closed behavior before any real mutation occurs.

## 4. Batch-first implementation package

Normal coherent implementation is:

`implementation + targeted tests + independent validator + CLI/orchestration + documentation/status`

Default cadence is **batch-first**:

- implement as much of the current phase as can be safely and coherently completed in one development batch;
- if the entire phase is well-defined and no external/authority boundary interrupts it, implement the whole phase before the first formal full-regression boundary;
- combine related production code, tests, validators, orchestration, diagnostics, and documentation work instead of creating artificial substeps;
- use focused tests during development when they provide useful feedback, especially around new contracts, risky shared code, or recently failing paths;
- do not run the entire regression suite after every small commit merely for ceremony;
- do not stop for user interaction when the remaining work can be completed safely with repository/CI evidence alone;
- if an intermediate test reveals a genuine architectural, security, data-integrity, or authority defect, fix that defect before stacking additional work on top of it.

The preferred unit of work is the **largest coherent batch that preserves clear causality and can still be validated meaningfully**.

## 5. Validation ladder and cadence

Validation normally proceeds through these layers:

1. static/syntax/compile checks as useful during development;
2. focused unit/contract tests for changed/high-risk packages as useful during development;
3. independent phase validator before the acceptance evidence boundary;
4. full local regression at a meaningful batch/phase boundary;
5. Windows and Ubuntu CI at that evidence boundary;
6. target-machine/provider evidence only when CI cannot reproduce the required environment;
7. reconciliation/audit evidence for provider or authority-changing work.

Cadence rules:

- **Whole-phase batch preferred:** when feasible, finish the implementation package and then run the independent validator + full regression + cross-platform CI once as the primary evidence boundary.
- **Intermediate full regression only when justified:** use it after broad shared-foundation changes, before an irreversible/external step, when a focused failure suggests wider regression risk, or when the phase is large enough that an interim evidence boundary materially reduces debugging risk.
- **Focused tests are cheap feedback:** run them freely while coding, but they do not replace the final validator/regression/CI evidence.
- **Target-machine work is scarce evidence:** do not repeatedly ask the user to rerun local/provider checks when code relevant to that evidence has not changed.
- **Documentation sync is batched:** update living docs at meaningful evidence boundaries and acceptance transitions, not after every minor edit.

A failure at any layer is investigated at that layer. ATLAS does not weaken data, risk, provider, security, or trading gates merely to obtain a green result.

## 6. Target-machine and provider rule

Target-machine execution is required only when the evidence cannot be established in CI or mocks, including real credentials, real broker reads, realtime market state, or explicitly authorized paper/live mutations.

For provider mutations:

- authorization must be explicit for the exact authority class;
- unknown or uncertain provider state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when the phase contract says it is separate;
- live-money authority is never inferred from paper/sandbox authority.

**Authority boundaries override batching.** A coherent phase may be implemented in one batch, but ATLAS may not batch across an explicit user-authorization checkpoint, an external provider-state prerequisite, or a separate destructive/live authority class.

## 7. Acceptance and merge

A phase may be marked **ACCEPTED** only when:

- required implementation is complete;
- required focused/contract tests pass;
- independent validator passes;
- required full regression/CI passes;
- required target-machine/provider evidence is accepted;
- uncertainty and negative-path behavior have been tested;
- living documentation and PR evidence are synchronized;
- no unresolved blocker remains inside the phase acceptance boundary.

After acceptance:

1. mark the PR ready if it was draft;
2. perform final merge-readiness checks;
3. merge to `main`;
4. verify `main` state/CI as appropriate;
5. delete the merged phase branch;
6. update living status to `MERGED`;
7. define and lock the next numbered phase before substantive implementation starts.

## 8. Documentation contract

Every meaningful batch/evidence boundary updates, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- this phase-flow contract when the process itself changes;
- active phase specification;
- active PR acceptance/evidence ledger;
- configuration documentation/templates when configuration changes.

Historical phase/fix documents remain provenance rather than current instructions.

## 9. Current application — Phase 18

Phase 18 is **Paper Provider Mutation Lifecycle Validation**.

Current subphase state:

### Phase 18A — Pre-mutation software validation

**State: ACCEPTED / COMPLETE**

Evidence includes:

- Phase 18 authority gate and lifecycle implementation;
- fake-provider production semantic coverage;
- separate operational validation-order path;
- independent Phase 18 validator;
- target-machine focused validation;
- final target-machine full regression: 908 passed;
- Windows/Ubuntu CI green;
- Windows loopback portability issue closed;
- no provider mutation performed.

### Phase 18B — Real paper-provider operational certification

**State: WAITING_EXTERNAL**

Waiting conditions:

- regular U.S. equity market session;
- accepted Massive realtime focused quote state;
- plan-only validation first;
- explicit paper-provider mutation authorization before the first real write.

Required lifecycle:

`realtime quote -> plan-only one-share validation -> review -> explicit authorization -> Webull sandbox submit once -> exact reconcile -> cancel once if still open -> exact reconcile flat -> sanitized evidence -> Phase 18 acceptance/merge`

If the order fills or partially fills, ATLAS stops for separate cleanup authority. Alpaca is not an automatic failover destination. Live trading remains outside Phase 18.

Phase 18 demonstrates the batching rule: 18A was developed and validated as a coherent software package; 18B exists separately only because regular-session realtime evidence and explicit provider-mutation authority are genuine external/authority boundaries.

## 10. Next-phase rule

Phase 19 is **not active yet**.

The next numbered phase will be defined only after Phase 18B evidence is accepted and Phase 18 is merged. Its purpose, scope, authority, tests, evidence, and acceptance criteria must be written before substantive Phase 19 implementation begins.

Once Phase 19 is locked, the default is to implement **as much of Phase 19 as possible — preferably the full phase — before stopping for the formal evidence boundary**, unless measured risk, an external prerequisite, or an authority checkpoint makes an earlier boundary materially useful.
