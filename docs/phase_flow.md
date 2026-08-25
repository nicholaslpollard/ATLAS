# ATLAS Phase Execution Flow

**Normative development-flow contract. Last synchronized: 2026-08-24.**

This document defines how ATLAS moves between numbered phases. It prevents scope drift, skipped evidence boundaries, accidental authority expansion, and ad hoc tuning while still favoring efficient coherent batches.

## 1. Core rule

ATLAS advances by explicit numbered phases:

`DEFINE -> LOCK -> IMPLEMENT COHERENT BATCH -> DEVELOP/FOCUSED TEST AS NEEDED -> INDEPENDENT VALIDATE -> FULL REGRESSION/CI AT EVIDENCE BOUNDARY -> TARGET EVIDENCE IF REQUIRED -> DOCUMENT -> ACCEPT -> MERGE -> NEXT PHASE`

The flow is a control framework, not a requirement to stop after every arrow. When scope is sufficiently defined and no external/authority checkpoint interrupts it, implement the largest safe coherent batch.

No credential, endpoint, connected account, implementation detail, available adapter, local file, or passing CI silently expands provider, broker, strategy-support, automation, or LIVE authority.

## 2. Phase states

- **PLANNED** — rough roadmap position known; implementation not started.
- **STACKED_PREP** — next-phase work developed on a merge-blocked branch while current work waits on a genuine external condition.
- **ACTIVE** — scope/authority locked and implementation/evidence work underway.
- **WAITING_EXTERNAL** — software is ready but acceptance requires market/provider/target-machine/user-authority evidence.
- **BLOCKED** — a defect, missing prerequisite, or unresolved authority/data issue prevents progress.
- **VALIDATED / MERGE PENDING** — implementation and required evidence are green; documentation/final merge work remains.
- **ACCEPTED** — implementation, validation, target evidence, documentation, and negative paths are satisfied.
- **MERGED** — accepted phase is merged to `main`.

Unnumbered maintenance/stabilization may occur between merged phases when it changes no numbered-phase authority. It must still be validated/documented when it changes shared foundations or living handoff state.

## 3. Required phase definition

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

Research phases that select models, strategies, thresholds, or policies must also preregister the relevant search/selection methodology before protected or final evidence is read. A zero-winner result is valid.

## 4. Batch-first implementation package

Normal coherent package:

`implementation + targeted tests + independent validator + CLI/orchestration as applicable + documentation/status`

Rules:

- prefer the largest safe coherent batch;
- combine related production code, tests, validators, orchestration, diagnostics, and documentation;
- focused tests do not replace final regression/CI;
- do not run full CI after every trivial edit solely for ceremony;
- do not stop for user interaction when remaining work can be completed safely with repo/CI evidence;
- fix genuine architecture/security/data/authority defects before stacking more work;
- never weaken data, strategy, risk, provider, security, or trading gates merely to obtain green tests or nonzero activity.

## 5. Validation ladder

Normal layers:

1. syntax/static/compile checks as useful;
2. focused unit/contract tests;
3. independent phase validator;
4. full regression at a meaningful evidence boundary;
5. Ubuntu + Windows CI;
6. target-machine/provider evidence only when CI/mocks cannot establish the fact;
7. reconciliation/audit evidence for real mutation or authority-changing work.

Target-machine work is scarce evidence and should not be repeated when relevant code/inputs have not changed. Documentation sync is batched at evidence/acceptance transitions.

## 6. Target-machine/provider rule

Target-machine execution is required only when the required evidence cannot be established in CI/mocks, including local accepted data-lake artifacts, real credentials, provider entitlements, realtime/finalized market state, broker reads, or explicitly authorized provider mutations.

For provider mutations:

- authorization is explicit for the exact authority class;
- unknown/uncertain state fails closed;
- no blind mutation retry;
- no automatic cross-broker failover;
- cleanup/flatten authority is separate when the contract says so;
- LIVE authority is never inferred from PAPER/sandbox authority.

For provider reads under explicit scope:

- provider-free prepare identifies the exact missing read class and deterministic run scope;
- only the authorized class may be performed;
- stale/mismatched authority fails closed;
- acquisition does not silently expand downstream authority;
- entitlement/session gaps are surfaced rather than hidden.

For zero-case/no-winner evidence:

- zero cases, zero promotions, zero strategy finalists, and zero provider calls are valid when they follow accepted upstream evidence;
- do not fabricate a ticker/case, lower thresholds, inject arbitrary trade inputs, or rerun unrelated certification mutations merely to obtain activity;
- preserve the zero result as evidence of correct fail-closed behavior.

For failed/partial analytical runs:

- newer local files do not become accepted state merely because they exist;
- the accepted handoff/manifest remains authoritative;
- reruns recover from the last accepted baseline unless validated resumability explicitly says otherwise;
- valid partial provider reads may be reused only after a new provider-free inventory proves them present.

## 7. Research/protected-evidence rule

When a phase performs model/strategy/policy selection:

- define the candidate/search space before protected evidence is read;
- define selection metrics, dependence treatment, multiplicity control, minimum evidence, costs/stress, and temporal validation before evaluation;
- keep selection and protected/final evidence physically and logically separated where practical;
- write/fingerprint selection locks before internal/protected validation when the contract requires it;
- do not revisit losing alternatives after seeing internal/protected results unless a new separately preregistered research phase is started;
- do not reinterpret a conservative failure as permission to relax the gate;
- if no candidate earns protected-evidence access, do not open the protected set.

Descriptive post-run forensics may explain why a locked study failed, but may not retroactively modify the locked thresholds or turn failed candidates into accepted ones.

## 8. Acceptance and merge

A phase may be ACCEPTED only when:

- required implementation is complete;
- focused/contract tests pass;
- independent validator passes;
- required full regression/CI passes;
- required target-machine/provider evidence is accepted;
- uncertainty and negative paths are tested;
- living docs and PR evidence are synchronized;
- no unresolved blocker remains;
- stacked upstream, if any, is merged/revalidated.

After acceptance:

1. mark draft PR ready;
2. perform merge-readiness checks;
3. merge to `main`;
4. verify authoritative main state/CI as appropriate;
5. delete merged branch when practical;
6. synchronize living status to MERGED and record authoritative merge SHA;
7. define/lock the next numbered phase before substantive next-phase work.

If the merge/document sequence drifts procedurally, record it explicitly and perform an unnumbered no-authority maintenance closeout before the next numbered phase.

## 9. Documentation contract

Every meaningful boundary updates as applicable:

- `README.md`;
- `docs/roadmap.md`;
- `docs/current_status.md`;
- this file when current application/process is stale;
- active phase specification;
- PR evidence;
- configuration docs/templates.

Historical phase/fix docs remain provenance rather than current instructions.

## 10. Current application — Phase24 acceptance evidence complete

Accepted upstream:

- **Phases 1–23 ACCEPTED / MERGED**;
- Phase23 PR #25 merged at `2004338624766c42b5f4db2bb0976b2047a5c6b0`;
- Phase23 target cycle through 2026-08-21: 23 WARM/HOT directional cases, 0 promotions, zero downstream execution cases, independent PASS.

Phase24 PR #26 is at **VALIDATED / MERGE PENDING** with disposition **NO SUPPORT REPLACEMENT**.

Phase24 evidence sequence:

1. Gate0 provider-free diagnostic proved incumbent rules are not dormant: 92 eligible route evaluations, 48 counterfactual fires, 21/23 current cases with >=1 fire; authority remained zero.
2. Gate1 preregistered exactly 28 bounded challengers and the stronger v2 evidence framework before challenger performance was observed.
3. Gate1 fingerprint: `9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`.
4. Gate2 target head `f591942413973107d7abc9d21325623e2e7000f1` evaluated development-only evidence and returned 0 basic-pass, 0 selections, 0 finalists, 0 protected reads, independent PASS.
5. Post-Gate2 read-only forensics showed all 28 challengers failed positive chronological folds, positive block-bootstrap LCB, and positive 25 bps stress mean; sample scarcity was not the general problem.
6. Short-side trend/momentum/breakdown families were materially negative at 10 bps; mirrored LONG/SHORT design is not assumed valid.
7. Phase24 closeout head `ba0721dd717ae8bdda877a376549cdef69ca00d9` passed exact-head CI run `32806363124` on Ubuntu and Windows, every validator through Gate2 plus full regression.
8. Phase11 support remains unchanged: SUPPORTED 0, MIXED 3, UNSUPPORTED 5.
9. No Gate3 protected evaluation is authorized for the zero-finalist set.

## 11. Next-phase boundary

After Phase24 merges, the next phase should not continue ad hoc threshold tuning. The post-evidence code audit found that historical strategy support and production promotion are evaluated on different populations:

- historical study: broad daily rows plus broad market-regime route;
- production: WARM/HOT discovery -> discovery direction -> market/sector/ticker route -> support -> current rule firing.

Ticker/intraday regime history legitimately begins **2021-08-16**; pre-2021 intraday context must not be fabricated.

Therefore DEFINE/LOCK **Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence** before substantive implementation. Initially hold strategy rules and the three-session outcome fixed; reconstruct the PIT production-path population and measure whether conditioning on the population ATLAS actually tries to trade changes strategy evidence.

If route-fidelity evidence still has no robust edge, a later separately preregistered challenger process may investigate materially different families such as relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite strategies.

Preserve Phase21/22 PAPER authority, Phase13/14 independence, LIVE disablement, and no automatic broker failover. GUI remains monitoring/control only. Scheduler and PostgreSQL runtime promotion remain separate future authority decisions.
