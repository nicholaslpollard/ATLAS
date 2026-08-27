# ATLAS Phase Execution Flow

**Normative phase-as-gate development contract. Re-baselined: 2026-08-26.**

Read `docs/roadmap.md` first for the mission and remaining phase sequence. This file controls how each numbered phase is executed and accepted.

## 1. Core rule — the phase is the gate

Starting with Phase26, **each numbered phase is one project acceptance gate**.

A phase can contain many implementation tasks, research steps, work packages, checkpoints, local experiments, preregistration steps, development tests, internal/protected evidence splits, or repair cycles. Those are not separate project gates and should not be presented as separate phases.

Normal lifecycle:

`DEFINE/LOCK PHASE -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

The goal is to move quickly through coherent work while keeping the final evidence bar high.

## 2. DEFINE / LOCK

Before material implementation or target-performance inspection, the active phase specification must state in plain language:

- purpose and why it advances the ATLAS end goal;
- entry conditions and accepted upstream evidence;
- exact scope and explicit non-scope;
- authority allowed during the phase and authority that remains forbidden;
- data/source/model/strategy versions that are authoritative;
- expected artifacts/deliverables;
- success/failure/negative-result semantics;
- phase-end acceptance criteria;
- target-machine/provider/broker evidence required, if any;
- rollback/recovery expectations when state can mutate.

For research phases, also freeze the search space/hypotheses, outcomes, chronology, costs, dependence treatment, multiplicity/selection-bias treatment, robustness checks, and protected-evidence boundary before protected results are inspected.

A phase definition may be corrected if it contains a factual or methodological defect, but it may not be weakened after seeing disappointing results merely to force acceptance or trading activity.

## 3. IMPLEMENT COHERENT WORK

Use the largest safe coherent work package rather than conversational micro-steps.

During implementation:

- reuse accepted components instead of creating parallel paths without measured need;
- keep interfaces, authority boundaries, lineage, and deterministic behavior explicit;
- add focused tests as code changes;
- run local diagnostics when useful;
- repair defects immediately when evidence is clear;
- continue through ordinary read-only/reversible work without unnecessary operator stops.

Operator interaction is reserved for facts that repository/CI cannot establish, genuine product decisions, credentials/provider evidence, real broker mutations, destructive actions, or authority-changing operations.

## 4. Development testing is not acceptance

Focused/unit tests during implementation are encouraged because they shorten feedback loops. A successful focused test does **not** mean the phase passed.

Likewise, a script producing output, a provider responding successfully, a backtest producing profit, a paper order submitting, or an AI review completing does not independently accept a phase.

Only the complete phase-end gate accepts the phase.

## 5. Full phase-end acceptance gate

Every phase must run the complete applicable validation stack **after the phase work is finished**.

Unless genuinely inapplicable and documented, the phase-end gate includes:

1. syntax/compile/static checks supported by the repository;
2. all phase-focused unit/contract/integration tests;
3. an independent validator or equivalent independent verification of the new capability/evidence;
4. every retained historical validator needed to prove no accepted authority/regression was broken;
5. the complete repository regression test suite;
6. Ubuntu + Windows CI on the exact acceptance head;
7. negative/adversarial/error-path testing appropriate to the phase;
8. restart/idempotency/recovery/reconciliation testing whenever stateful or external operations are involved;
9. target-machine/provider/broker evidence only when mocks/CI cannot establish the required fact;
10. reproducibility/lineage checks for analytical/research/model results;
11. confirmation that forbidden provider/broker/PAPER/LIVE/support/automation writes remained zero unless explicitly authorized by the phase;
12. synchronization of the roadmap, current status, active phase document, README/other living docs where needed.

The exact tested/documented head is the only candidate for acceptance and merge.

## 6. Phase outcomes

A phase ends in one of three project states:

### ACCEPTED — POSITIVE

The implementation/evidence passed the full gate and earned the capability/authority explicitly defined by the phase.

### ACCEPTED — NEGATIVE

A preregistered research/question phase passed technically and scientifically but found no acceptable candidate/edge/replacement. This is valid evidence. It grants no authority that depended on a positive result.

### NOT ACCEPTED

Implementation, evidence, validation, CI, target evidence, recovery, or a mandatory acceptance criterion failed. Repair within the same phase and rerun the full phase-end gate. Do not create a new phase merely to avoid repairing the active phase.

## 7. Research-specific rules

Research phases must distinguish exploration from confirmation.

- Protected/final evidence remains untouched until frozen candidate definitions and acceptance methodology exist.
- Losing alternatives are not revived after protected evidence without a newly declared future research phase.
- Multiple testing, repeated optimization, data snooping, and backtest overfitting must be treated as first-class risks.
- Point-in-time populations and chronology are mandatory.
- Costs/market frictions must be appropriate to the instrument/strategy, not selected to make results pass.
- Dependence among overlapping outcomes or same-session cross-sectional observations must not be treated as independent evidence.
- Zero finalists is a valid phase result when produced under the frozen methodology.

Internal labels such as `work package`, `checkpoint`, `development split`, `internal validation`, or `protected confirmation` are allowed. Do not create future project progress labels such as `Gate0`, `Gate1`, etc. inside a numbered phase unless an external technical standard requires that term. **The numbered phase is the gate.**

## 8. Provider/broker/mutation authority

Credentials, endpoints, connected accounts, local artifacts, passing tests, or prior successful calls never create authority.

Read-only provider work may use a bounded explicit CLI command as authorization when the active phase says so. Real mutations, destructive cleanup, PAPER submits, broker switching, order/position changes, and LIVE require the exact authority defined for that operation.

Unknown or uncertain mutation state fails closed. Reconcile before retry. Never blindly retry an ambiguous submit/cancel/replace/close operation.

Automatic cross-broker failover remains forbidden. PAPER never implies LIVE.

## 9. User-facing phase closeout

Every phase completion report must first provide this plain-English summary:

1. **Goal** — what the phase was supposed to accomplish.
2. **Built** — what changed.
3. **Full gate** — PASS/FAIL and the full regression/CI result.
4. **Evidence meaning** — what the result means without requiring the operator to interpret raw statistics/hashes.
5. **Authority change** — what ATLAS may now do that it could not do before, or `NONE`.
6. **Limitations/risks** — what remains unproven or blocked.
7. **Next phase** — exact next objective and why.

Detailed row counts, fingerprints, hashes, statistical tables, CI IDs, and validator outputs follow afterward as the audit record.

## 10. Current application

- **Phases 1–25: ACCEPTED / MERGED.**
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950`.
- Phase25 target-tested code: `302bf6db5d807884f3b74cda049fc95864c5a194`; CI `32981080421` passed Ubuntu/Windows.
- Phase25 final docs head: `f2d10465b71446b253b5d73a50845d2ea1e704d3`; CI `33025699177` passed Ubuntu/Windows.
- Phase25 accepted negative result: `NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED`.
- Phase11 support remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.
- **Phase26 is the active next gate: Production-Path-Native Alpha Discovery & Validation.**

Phase26 is responsible for the whole alpha-discovery/validation question defined in the master roadmap. Its internal research stages are work packages/checkpoints, not separate project gates. The phase ends only after the full Phase26 acceptance suite and any required protected evidence are complete.

Preserve all existing data integrity, execution, risk, AI-independence, broker, browser, scheduler/PostgreSQL, and LIVE authority boundaries unless a later numbered phase explicitly earns a change.
