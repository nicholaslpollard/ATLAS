# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-24.**

This document defines how ATLAS moves from one numbered phase to the next. It prevents scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc development without turning normal work into unnecessary micro-checkpoints.

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a control framework, not a requirement to stop after every arrow. When a phase is sufficiently defined and no authority/external checkpoint interrupts it, implement the largest coherent batch and validate at the meaningful evidence boundary.

No credential, endpoint, connected account, implementation detail, prior success, available adapter, or passing CI silently expands provider or LIVE authority.

## 2. Phase states

- **PLANNED** — rough roadmap position known; implementation not started.
- **STACKED_PREP** — next-phase work developed on a merge-blocked stacked branch while current phase is waiting on a genuine external condition.
- **ACTIVE** — scope/authority locked and implementation/evidence work underway.
- **WAITING_EXTERNAL** — software is ready but acceptance requires market/provider/target-machine/user-authority evidence.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **VALIDATED / MERGE PENDING** — implementation and its primary evidence boundary are green; documentation/final exact-head acceptance/merge work remains.
- **ACCEPTED** — all implementation, validation, target evidence, documentation, and negative-path criteria are satisfied.
- **MERGED** — accepted phase is merged to `main`.

Unnumbered maintenance/stabilization may occur between merged phases only when it changes no numbered-phase authority. It must still be validated and documented when it changes shared foundations.

## 3. Stacked-preparation exception

When the current merge-authoritative phase is `WAITING_EXTERNAL`, independent next-phase preparation may proceed only if:

1. current blocking condition is genuinely external rather than unfinished software;
2. stacked branch is based on current phase head;
3. stacked PR targets current phase branch, not `main`;
4. stacked PR remains draft/merge-blocked;
5. stacked work does not change/bypass current provider/LIVE authority;
6. it performs no real provider mutation unless separately authorized by current phase;
7. after upstream merge it is rebased/retargeted and revalidated against merged upstream;
8. next phase cannot be accepted/merged before its declared upstream is merged.

This exception improves throughput, not authority overlap.

## 4. Required phase definition

Before substantive implementation, an ACTIVE or STACKED_PREP phase must state:

1. number/name;
2. purpose;
3. upstream binding;
4. exact scope;
5. non-goals;
6. authority boundary;
7. dependencies;
8. deliverables;
9. validation/acceptance criteria;
10. target-machine/external evidence requirements;
11. failure/uncertainty behavior;
12. documentation to synchronize at acceptance.

Authority-changing phases must preregister exact authorization and fail-closed behavior before any real mutation.

## 5. Batch-first implementation package

Normal coherent package:

`implementation + targeted tests + independent validator + CLI/orchestration as applicable + documentation/status`

Rules:

- prefer the largest safe coherent batch;
- combine related production code, tests, validators, orchestration, diagnostics, and documentation;
- focused tests are useful during development but do not replace final regression/CI;
- do not run the full suite after every tiny change merely for ceremony;
- do not stop for user interaction when remaining work can be completed safely with repo/CI evidence;
- fix genuine architecture/security/data/authority defects before stacking more work on top.

## 6. Validation ladder and cadence

Normal layers:

1. syntax/static/compile checks as useful;
2. focused unit/contract tests;
3. independent phase validator;
4. full regression at a meaningful boundary;
5. Ubuntu + Windows CI;
6. target-machine/provider evidence only when CI/mocks cannot establish the required fact;
7. reconciliation/audit evidence for real mutation or authority-changing work.

Cadence:

- whole-phase batch preferred when feasible;
- intermediate full regression only when broad shared changes, irreversible/external action, or failure evidence justifies it;
- target-machine work is scarce evidence and should not be repeated when relevant code has not changed;
- documentation sync is batched at evidence/acceptance transitions;
- stacked prep gets its own CI and is revalidated after upstream merge.

Never weaken data, risk, provider, security, or trading gates merely to obtain green tests.

## 7. Target-machine/provider rule

Target-machine execution is required only when the required evidence cannot be established in CI/mocks, including real credentials, broker reads, realtime market state, or explicitly authorized provider mutations.

For provider mutations:

- authorization must be explicit for the exact authority class;
- unknown/uncertain provider state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when its contract says so;
- LIVE authority is never inferred from PAPER/sandbox authority.

Authority boundaries override batching and stacked preparation.

## 8. Acceptance and merge

A phase may be ACCEPTED only when:

- required implementation complete;
- focused/contract tests pass;
- independent validator passes;
- required full regression/CI passes;
- required target-machine/provider evidence is accepted;
- uncertainty and negative paths tested;
- living docs and PR evidence synchronized;
- no unresolved blocker remains;
- stacked upstream, if any, is merged and revalidated.

After acceptance:

1. mark draft PR ready;
2. perform merge-readiness checks;
3. merge to `main`;
4. verify authoritative main state/CI as appropriate;
5. delete merged branch when practical;
6. synchronize living status to MERGED;
7. define/lock the next numbered phase before substantive next-phase work.

## 9. Documentation contract

Every meaningful boundary updates as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- this file when current application/process becomes stale;
- active phase specification;
- PR evidence;
- configuration docs/templates.

Historical phase/fix docs remain provenance rather than current instructions.

## 10. Current application — Phase 21 validated / merge pending

Accepted upstream:

- **Phases 1–20 ACCEPTED / MERGED**;
- Phase18 merge `55bdd7446f0bbd4225de264187c7f5fb601991b0`;
- Phase19 merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- Phase20 merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`;
- Phase20 fingerprint `b4f9bd37c3c425e182e4a0da255e8a903d95101d119c833c38c7fd2c0cd3741a`;
- post-Phase20 anti-drift baseline `4afe8e0a5238b176edd47eb6e70359ccff6d65b1`.

Current phase:

- **Phase21 — Unified Paper Execution Authority and Operational Binding: VALIDATED / MERGE PENDING**;
- branch `phase-21-unified-paper-execution-authority`;
- PR #22 draft until final acceptance;
- policy `phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`;
- fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`;
- validated implementation head `d3599f3a184142de4ac5f03b58fc355f0bb11001`;
- CI `32781962354`: Ubuntu **964 passed in 15.42s**, Windows **964 passed in 24.52s**, every validator through Phase21 PASS;
- provider calls/writes/broker writes during Phase21 validation: 0/0/0.

Current Phase21 authority lock:

- every new real PAPER provider submit crosses one centralized default-deny seam;
- Webull PAPER + Alpaca PAPER require exact broker/PAPER/run-scoped authority;
- exactly one raw `adapter.submit(plan)` exists under `packages/`, in execution engine;
- existing deterministic-order reuse performs no new mutation and needs no new mutation authority;
- SHADOW remains unchanged;
- original Phase18 explicit certification authorization remains separate and must pass before its narrow Phase21 compatibility authority is constructed;
- both Phase18 standard lifecycle and operational-validation path cross the central seam;
- Phase15 validates PAPER authority before live quote resolver initialization;
- browser cannot acquire Phase21 authority;
- Phase20 external mutation-stage registration remains blocked;
- LIVE and automatic failover remain disabled.

The first Phase21 CI exposed a real direct-submit bypass in `phase18_operational_validation.py`. That defect was fixed without weakening the independent validator. The validator now enforces exactly one raw submit seam.

Current closeout sequence:

1. synchronize Phase21 spec + living docs + PR evidence;
2. run documentation-head full cross-platform CI;
3. if green, mark Phase21 ACCEPTED in living docs and run final exact-head CI;
4. mark PR ready and merge to `main`;
5. verify main;
6. audit merged code for the smallest next operational gap toward routine Webull-primary PAPER execution/reconciliation/observability/outcomes;
7. define/lock the next numbered phase from that evidence.

No additional real provider mutation is required merely to close Phase21 because accepted Phase18 already proves target Webull sandbox submit/reconcile/cancel behavior. Phase21 itself is an internal authority-boundary hardening phase.

Phase21 does **not** imply autonomous scheduling, PostgreSQL runtime promotion, cleanup/flatten authority, broker switching, automatic failover, browser execution, or LIVE authority.
