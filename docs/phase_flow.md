# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-23.**

This document defines how ATLAS work moves from one numbered phase to the next. It exists to prevent scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc development that bypasses the roadmap **without turning the phase process into unnecessary micro-checkpoints**.

## 1. Core rule

ATLAS advances by explicit numbered phases.

A phase is not complete merely because code exists or tests pass. A normal phase moves through:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a **control framework, not a requirement to stop after each arrow**. When a whole phase is sufficiently defined, dependencies are available, and authority does not require an intermediate user/external checkpoint, ATLAS should implement the entire phase as one coherent batch and then perform the strongest required validation at the phase evidence boundary.

No credential, endpoint, connected account, implementation detail, prior phase success, or passing CI silently expands provider or live-trading authority.

## 2. Phase states

Every phase/subphase uses one of these states:

- **PLANNED** — purpose and rough roadmap position are known; implementation has not started.
- **STACKED_PREP** — next-phase work is being developed on a separate merge-blocked stacked branch while the current phase is `WAITING_EXTERNAL`; it is not yet merge-authoritative.
- **ACTIVE** — scope/authority are locked and implementation/evidence work is underway as the current merge-authoritative phase.
- **WAITING_EXTERNAL** — implementation is ready but acceptance requires an external condition such as market hours, provider access, target-machine evidence, or explicit user authorization.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **ACCEPTED** — all phase acceptance criteria and required evidence are satisfied.
- **MERGED** — accepted phase is merged to `main`; its branch may then be removed.

A subphase may be used when a phase contains a genuine authority or external-condition boundary. Subphases do not become independent roadmap phases unless explicitly promoted to a numbered phase.

## 3. Stacked-preparation exception

When the current merge-authoritative phase is `WAITING_EXTERNAL`, development time should not be wasted if the next phase contains independent, non-authority-changing work.

A next-phase **STACKED_PREP** branch is allowed only when all of the following hold:

1. the current phase is blocked only by a real external/authority condition rather than unfinished software;
2. the stacked branch is created from the current phase branch/head so accepted upstream work is present;
3. its PR targets the current phase branch, not `main`;
4. the stacked PR is draft/merge-blocked until the current phase is accepted and merged;
5. stacked work does not change or bypass the current phase's provider/live authority boundary;
6. stacked work performs no real provider mutation unless separately authorized by the current active phase contract;
7. after the upstream phase merges, the stacked branch/PR must be rebased or retargeted to `main` and revalidated against the actual merged upstream;
8. the next phase cannot be marked `ACCEPTED` or merged before its declared upstream phase is merged.

This exception exists to improve development throughput, not to permit authority overlap. Read-only observability, frontend work, orchestration, analytics, tests, and other non-mutating functionality are preferred stacked-prep candidates.

## 4. Required phase definition

Before implementation begins, an `ACTIVE` or `STACKED_PREP` phase must state:

1. phase number and name;
2. purpose;
3. accepted/planned upstream phase/commit/artifact binding;
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

## 5. Batch-first implementation package

Normal coherent implementation is:

`implementation + targeted tests + independent validator + CLI/orchestration + documentation/status`

Default cadence is **batch-first**:

- implement as much of the phase as can be safely and coherently completed in one development batch;
- if the entire phase is well-defined and no external/authority boundary interrupts it, implement the whole phase before the first formal full-regression boundary;
- combine related production code, tests, validators, orchestration, diagnostics, and documentation instead of creating artificial substeps;
- use focused tests during development when they provide useful feedback, especially around new contracts, risky shared code, or recently failing paths;
- do not run the entire regression suite after every small commit merely for ceremony;
- do not stop for user interaction when remaining work can be completed safely with repository/CI evidence alone;
- if an intermediate test reveals a genuine architectural, security, data-integrity, or authority defect, fix that defect before stacking additional work on top of it.

The preferred unit of work is the **largest coherent batch that preserves clear causality and can still be validated meaningfully**.

## 6. Validation ladder and cadence

Validation normally proceeds through these layers:

1. static/syntax/compile checks as useful during development;
2. focused unit/contract tests for changed/high-risk packages as useful during development;
3. independent phase validator before the acceptance evidence boundary;
4. full local regression at a meaningful batch/phase boundary when local evidence is useful;
5. Windows and Ubuntu CI at that evidence boundary;
6. target-machine/provider evidence only when CI cannot reproduce the required environment;
7. reconciliation/audit evidence for provider or authority-changing work.

Cadence rules:

- **Whole-phase batch preferred:** when feasible, finish the implementation package and then run the independent validator + full regression + cross-platform CI once as the primary evidence boundary.
- **Intermediate full regression only when justified:** use it after broad shared-foundation changes, before an irreversible/external step, when a focused failure suggests wider regression risk, or when a phase is large enough that an interim boundary materially reduces debugging risk.
- **Focused tests are cheap feedback:** run them freely while coding, but they do not replace final validator/regression/CI evidence.
- **Target-machine work is scarce evidence:** do not repeatedly ask the user to rerun local/provider checks when code relevant to that evidence has not changed.
- **Documentation sync is batched:** update living docs at meaningful evidence boundaries and acceptance transitions, not after every minor edit.
- **Stacked prep gets its own CI:** validate a stacked branch against its stacked upstream, then revalidate after retarget/rebase to the merged upstream.

A failure at any layer is investigated at that layer. ATLAS does not weaken data, risk, provider, security, or trading gates merely to obtain a green result.

## 7. Target-machine and provider rule

Target-machine execution is required only when the evidence cannot be established in CI or mocks, including real credentials, real broker reads, realtime market state, or explicitly authorized paper/live mutations.

For provider mutations:

- authorization must be explicit for the exact authority class;
- unknown or uncertain provider state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when the phase contract says it is separate;
- live-money authority is never inferred from paper/sandbox authority.

**Authority boundaries override batching and stacked prep.** ATLAS may not batch across an explicit user-authorization checkpoint, an external provider-state prerequisite, or a separate destructive/live authority class.

## 8. Acceptance and merge

A phase may be marked **ACCEPTED** only when:

- required implementation is complete;
- required focused/contract tests pass;
- independent validator passes;
- required full regression/CI passes;
- required target-machine/provider evidence is accepted;
- uncertainty and negative-path behavior have been tested;
- living documentation and PR evidence are synchronized;
- no unresolved blocker remains inside the phase acceptance boundary;
- any stacked-prep upstream has actually merged and the phase was revalidated against that merged upstream.

After acceptance:

1. mark the PR ready if it was draft;
2. perform final merge-readiness checks;
3. merge to `main`;
4. verify `main` state/CI as appropriate;
5. delete the merged phase branch;
6. update living status to `MERGED`;
7. promote/retarget any valid stacked-prep next phase, or define and lock the next numbered phase before substantive new work starts.

## 9. Documentation contract

Every meaningful batch/evidence boundary updates, as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- this phase-flow contract when the process itself changes;
- active/stacked phase specification;
- active PR acceptance/evidence ledger;
- configuration documentation/templates when configuration changes.

Historical phase/fix documents remain provenance rather than current instructions.

## 10. Current application — Phase 18 / Phase 19 prep

Phase 18 is **Paper Provider Mutation Lifecycle Validation**.

### Phase 18A — Pre-mutation software validation

**State: ACCEPTED / COMPLETE**

Evidence includes the Phase 18 authority/lifecycle implementation, focused validation, independent validator, target-machine 908-test regression, Windows/Ubuntu CI, closed Windows loopback portability issue, and zero provider mutations during software acceptance.

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

### Phase 19 stacked preparation

Because Phase 18B is waiting only on an external market-hours/authorization boundary, Phase 19 may enter `STACKED_PREP` on a separate branch/PR under section 3. It remains merge-blocked until Phase 18 is accepted and merged.

The preferred Phase 19 direction is **Operations Dashboard & Paper/Shadow Observability**: read-only end-to-end ATLAS visibility and operator UX, with no new provider-write or live-trading authority.
