# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-24.**

This document defines how ATLAS moves from one numbered phase to the next. It prevents scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc development without turning normal work into unnecessary micro-checkpoints.

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a control framework, not a requirement to stop after every arrow. When a phase is sufficiently defined and no authority/external checkpoint interrupts it, implement the largest coherent batch and validate at the meaningful evidence boundary.

No credential, endpoint, connected account, implementation detail, prior success, available adapter, local file, or passing CI silently expands provider, broker, automation, or LIVE authority.

## 2. Phase states

- **PLANNED** — rough roadmap position known; implementation not started.
- **STACKED_PREP** — next-phase work developed on a merge-blocked stacked branch while current phase waits on a genuine external condition.
- **ACTIVE** — scope/authority locked and implementation/evidence work underway.
- **WAITING_EXTERNAL** — software is ready but acceptance requires market/provider/target-machine/user-authority evidence.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **VALIDATED / MERGE PENDING** — implementation and required evidence are green; documentation/final exact-head acceptance/merge work remains.
- **ACCEPTED** — all implementation, validation, target evidence, documentation, and negative-path criteria are satisfied.
- **MERGED** — accepted phase is merged to `main`.

Unnumbered maintenance/stabilization may occur between merged phases only when it changes no numbered-phase authority. It must still be validated and documented when it changes shared foundations or living handoff state.

## 3. Stacked-preparation exception

When the current merge-authoritative phase is `WAITING_EXTERNAL`, independent next-phase preparation may proceed only if:

1. the blocking condition is genuinely external rather than unfinished software;
2. the stacked branch is based on current phase head;
3. the stacked PR targets the current phase branch, not `main`;
4. stacked work remains draft/merge-blocked;
5. it does not change/bypass current provider/LIVE authority;
6. it performs no real provider mutation unless separately authorized by the current phase;
7. after upstream merge it is rebased/retargeted and revalidated against merged upstream;
8. the next phase cannot be accepted/merged before its declared upstream is merged.

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

Target-machine execution is required only when the required evidence cannot be established in CI/mocks, including real credentials, provider entitlements, realtime/finalized market state, broker reads, or explicitly authorized provider mutations.

For provider mutations:

- authorization must be explicit for the exact authority class;
- unknown/uncertain provider state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when its contract says so;
- LIVE authority is never inferred from PAPER/sandbox authority.

For provider reads under an explicit phase scope:

- provider-free prepare should identify the exact missing read class and deterministic run scope;
- only the authorized read class may be performed;
- stale/mismatched authority fails closed;
- successful local acquisition does not silently expand downstream provider authority;
- provider entitlement/session gaps must be surfaced, not hidden by silently changing the requested date.

For zero-case target evidence:

- a zero-case/no-provider disposition is valid when it follows accepted upstream evidence;
- do not fabricate a case, weaken support thresholds, inject arbitrary ticker/order inputs, or repeat unrelated certification mutations merely to obtain a provider write;
- preserve the zero-case result as evidence of fail-closed/no-op behavior.

For failed/partial analytical runs:

- newer local artifacts do not become accepted state merely because they exist;
- the applicable accepted handoff/manifest remains the authority boundary;
- reruns must recover from the last accepted baseline unless the phase explicitly supports a validated resumable checkpoint;
- partial external reads may be reused only when their local evidence is valid and the next provider-free prepare re-inventories them.

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
6. synchronize living status to MERGED and record the authoritative merge SHA;
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

## 10. Current application — Phase23 accepted/merged

Accepted upstream:

- **Phases 1–23 ACCEPTED / MERGED**;
- Phase23 PR #25 merged at `2004338624766c42b5f4db2bb0976b2047a5c6b0`;
- Phase23 policy fingerprint `00a33af23c1b5257280aee4ab08ec8b8f0444d5cae6dcb051ad4d029bff02518`;
- implementation/repair head `803d43e43e8931f03ba836a23b781a7c3d3ee687`;
- final pre-merge documentation head `99425a0fa04d2a4faf0b4477343d11434cebd885`.

Phase23 accepted authority:

- provider-free `prepare`;
- external read authority, when needed, is **only** `MASSIVE_MARKET_REFERENCE_READS`;
- zero broker reads/writes;
- zero broker/order mutations;
- no Phase21 submit authority;
- no Phase22 execution;
- no downstream research/news/options/AI calls under the frozen zero-SUPPORTED path;
- no scheduler/PostgreSQL/browser/LIVE/automatic-failover authority.

Phase23 target evidence:

1. initial provider-free prepare for finalized 2026-08-21 resolved accepted baseline 2026-08-14 and five sessions to advance;
2. exact market/reference read scope was authorized because finalized source files/snapshots were missing;
3. first execute failed closed on a real persisted-null deserialization defect (`previous_effective_state=NaN`), not on a provider/broker/strategy threshold issue;
4. repair normalized only that nullable persisted field and added recovery/completion guards without changing discovery thresholds, hysteresis, support, model, risk, or execution authority;
5. repair-head cross-platform CI passed: push run `32802151860`, PR run `32802154831`, **988 tests on each OS**, every validator through Phase23 PASS;
6. repaired prepare retained the accepted 2026-08-14 baseline despite partial newer files, found all Massive/reference inputs local, and required no additional external authority;
7. successful execute advanced Aug 17–21, considered **23 WARM/HOT directional cases**, promoted **0**, produced zero Phase12/13/14/Phase22-ready cases, recorded zero broker/order/PAPER/LIVE writes, and passed independent persisted validation;
8. final docs-head CI `32803119880` passed **988 tests on Ubuntu and Windows**; Windows completed in 33.87s;
9. PR #25 was marked ready and merged at `2004338624766c42b5f4db2bb0976b2047a5c6b0`.

The zero-promotion result is accepted evidence. The frozen Phase11 support state has **0 SUPPORTED strategies**. No threshold or support class is to be relaxed merely to obtain activity.

## 11. Next-phase boundary

No Phase24 scope is accepted yet.

Before substantive next-phase implementation:

1. audit authoritative merged Phase23 code/artifacts and the 2026-08-21 current strategy rejection evidence;
2. verify no higher-priority correctness/data-integrity blocker remains;
3. if the frozen zero-SUPPORTED set remains the principal blocker, DEFINE and LOCK a formal strategy challenger/support-replacement phase using preregistered historical/current out-of-sample evidence;
4. do not lower thresholds or reclassify MIXED strategies merely to create trades;
5. preserve Phase21/22 PAPER authority, Phase13/14 independence, LIVE disablement, and no automatic broker failover.

GUI work may consume stable Phase23 artifacts when scheduled, but the browser remains a monitoring/control surface with no execution authority. Scheduler and PostgreSQL runtime promotion remain separate future authority decisions.