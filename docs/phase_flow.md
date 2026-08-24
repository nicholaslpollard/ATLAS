# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-24.**

This document defines how ATLAS moves from one numbered phase to the next. It prevents scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc development without turning normal work into unnecessary micro-checkpoints.

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a control framework, not a requirement to stop after every arrow. When a phase is sufficiently defined and no authority/external checkpoint interrupts it, implement the largest coherent batch and validate at the meaningful evidence boundary.

No credential, endpoint, connected account, implementation detail, prior success, available adapter, or passing CI silently expands provider, broker, automation, or LIVE authority.

## 2. Phase states

- **PLANNED** — rough roadmap position known; implementation not started.
- **STACKED_PREP** — next-phase work developed on a merge-blocked stacked branch while current phase is waiting on a genuine external condition.
- **ACTIVE** — scope/authority locked and implementation/evidence work underway.
- **WAITING_EXTERNAL** — software is ready but acceptance requires market/provider/target-machine/user-authority evidence.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **VALIDATED / MERGE PENDING** — implementation and its primary evidence boundary are green; documentation/final exact-head acceptance/merge work remains.
- **ACCEPTED** — all implementation, validation, target evidence, documentation, and negative-path criteria are satisfied.
- **MERGED** — accepted phase is merged to `main`.

Unnumbered maintenance/stabilization may occur between merged phases only when it changes no numbered-phase authority. It must still be validated and documented when it changes shared foundations or living handoff state.

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
- fix genuine architecture/security/data/authority defects before stacking more work on top;
- never weaken a strategy/data/risk/authority gate merely to create nonzero output.

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

Never weaken data, risk, provider, security, strategy, or trading gates merely to obtain green tests or a nonzero trade population.

## 7. Target-machine/provider rule

Target-machine execution is required only when the required evidence cannot be established in CI/mocks, including real credentials, broker reads, realtime market state, or explicitly authorized provider mutations.

For provider mutations:

- authorization must be explicit for the exact authority class;
- unknown/uncertain provider state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when its contract says so;
- LIVE authority is never inferred from PAPER/sandbox authority.

For zero-case target evidence:

- a zero-case/no-provider disposition is valid when it follows accepted upstream evidence;
- do not fabricate a case, weaken support thresholds, inject arbitrary ticker/order inputs, or repeat unrelated certification mutations merely to obtain a provider write;
- preserve the zero-case result as evidence of fail-closed/no-op behavior.

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

If implementation is merged before required documentation/target closeout due procedural error, do not silently pretend the sequence was followed. Record the drift explicitly, perform an unnumbered no-authority maintenance closeout, validate it, and restore synchronized living state before the next numbered phase.

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

## 10. Current application — post-Phase22 documentation closeout

Accepted upstream:

- **Phases 1–22 ACCEPTED / MERGED**;
- Phase18 merge `55bdd7446f0bbd4225de264187c7f5fb601991b0`;
- Phase19 merge `8e697ca2cadbaf510291cafaa3dcb5f7a314ffbe`;
- Phase20 merge `3b34bc700f8a0241ca5716c6d18bcb89f0d45620`;
- Phase21 merge `ed9e156437e3924293b90f06620ebbe9534fab15`;
- Phase22 merge `15c0a997ec847764e41fbd525ff52aa8c58f96ac`.

Phase21 accepted authority:

- policy `phase21-policy-v1-unified-paper-execution-authority-run-scoped-default-deny`;
- fingerprint `0ad0add1345ceec62f65bab25ce43806dafac4a64177ffc9c219e9d6c87665e5`;
- final exact head `174110e3688a0b8c087555a56adafaab99905c66`;
- final CI `32782618589`;
- exactly one raw `adapter.submit(plan)` remains under `packages/`, in the execution engine;
- every new PAPER provider submit requires exact centralized authority;
- browser, Phase20, scheduler, LIVE, and automatic failover authority remain absent.

Phase22 accepted operator binding:

- policy `phase22-policy-v1-operational-paper-runner-webull-primary-explicit-run-authority`;
- fingerprint `1866f132831c5cab4436163ddae6f67a7cc4768fb6dfe444e826567a6946f577`;
- implementation head `68f16256c8f9976ae5b6283dde437e93fbe70155`;
- CI `32787337500`: Ubuntu **974 passed in 13.80s**, Windows **974 passed in 33.93s**, every validator through Phase22 PASS;
- Webull default/primary; Alpaca explicit manual selection;
- PAPER only;
- exact interactive Phase21 run authority for nonzero cases;
- no arbitrary ticker/quantity/price/geometry input;
- no new submit seam;
- provider calls/writes/broker writes during repository validation: 0/0/0.

Target-machine Phase22 evidence on 2026-08-24:

`python scripts/run_phase22_paper.py prepare --broker webull`

resolved accepted as-of `2026-08-14`, found **0 accepted execution cases**, required no explicit mutation authority, and returned `PREPARED_ZERO_PROVIDER_CALLS`. This is the correct accepted zero-case path. No `execute` call or fabricated trade is required merely to create a mutation.

Current maintenance:

- branch `maintenance/post-phase22-closeout`;
- documentation/status repair only;
- no numbered-phase authority change;
- must pass normal Ubuntu/Windows CI before merge.

After this maintenance merge:

1. verify synchronized `main` through Phase22;
2. audit the actual merged current-data/analysis runners and stage boundaries;
3. identify the smallest missing binding toward a routine **current** end-to-end analytical run that can naturally produce accepted Phase13/14 cases for Phase22;
4. define/lock Phase23 only from that evidence;
5. do not assume scheduler/PostgreSQL work is next;
6. keep LIVE and automatic failover disabled.

Phase23 is not yet active.