# ATLAS Phase Execution Flow

**Normative phase-as-gate development contract. Re-baselined: 2026-08-27 after Phase29 closeout.**

Read `docs/roadmap.md` first for the mission and remaining phase sequence. Read `docs/phase_plain_english_contract.md` for the required operator-facing communication format. This file controls how each numbered phase is executed and accepted.

## 1. Core rule — the phase is the gate

Starting with Phase26, **each numbered phase is one project acceptance gate**.

A phase can contain many implementation tasks, research steps, feasibility/provenance work packages, checkpoints, local experiments, preregistration steps, development tests, internal/protected evidence splits, or repair cycles. Those are not separate project gates and should not be presented as separate phases.

Normal lifecycle:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK PHASE -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

A failed check is evidence about the system, not an obstacle to route around. **Root cause must be identified and corrected at the layer that owns the defect before the phase can earn acceptance.** A bypass, relaxed validator, alternate special-case path, ignored discrepancy, changed threshold, or additional wrapper whose purpose is merely to convert a failure into a pass cannot satisfy this contract.

## 2. Plain-English phase start is mandatory

Before material implementation begins, provide the operator a concise plain-English phase-start explanation covering:

1. where ATLAS is now and what is blocking/progressing the project;
2. what this phase is trying to accomplish;
3. why it matters to the account-growth/profit objective;
4. what will materially be built or changed;
5. what will be tested at the end;
6. what success means;
7. what happens if the phase fails or produces a legitimate negative result;
8. what is explicitly not happening yet.

If GUI/web/deployment work is included, also identify what the operator will see/control, whether the UI is read-only or action-capable, the deployment maturity level, and which backend authority restrictions remain in force.

## 3. DEFINE / LOCK

Before material implementation or target-performance inspection, the active phase specification must state:

- purpose and why it advances the ATLAS end goal;
- entry conditions and accepted upstream evidence;
- exact scope and explicit non-scope;
- authority allowed during the phase and authority that remains forbidden;
- authoritative data/source/model/strategy versions;
- expected artifacts/deliverables;
- success/failure/negative-result semantics;
- phase-end acceptance criteria;
- target-machine/provider/broker/deployment evidence required, if any;
- rollback/recovery expectations when state can mutate.

For research phases, also freeze the search space/hypotheses, outcomes, chronology, costs, dependence treatment, multiplicity/selection-bias treatment, robustness checks, and protected-evidence boundary **before any performance evidence governed by those choices is inspected**.

A research phase may begin with a clearly non-performance-bearing data-feasibility/provenance step when feasibility itself must be established before a scientifically valid hypothesis contract can be defined. That step must inspect no target outcomes, may not rank candidate alpha ideas by performance, and remains internal work inside the same numbered phase. Once feasibility is established, the finite research contract must be frozen before development/target performance is read.

For GUI/web/deployment phases, also freeze the backend/API authority boundary, frontend capabilities, security boundary, deployment target, restart/recovery behavior, and what actions remain prohibited.

A phase definition may be corrected if it contains a factual or methodological defect, but it may not be weakened after seeing disappointing results merely to force acceptance or trading activity.

## 4. IMPLEMENT COHERENT WORK

Use the largest safe coherent work package rather than conversational micro-steps.

During implementation:

- reuse accepted components instead of creating parallel paths without measured need;
- keep interfaces, authority boundaries, lineage, and deterministic behavior explicit;
- add focused tests as code changes;
- run local diagnostics when useful;
- repair defects immediately when evidence is clear;
- trace failures to the component, data artifact, assumption, interface, or process that owns them;
- do not introduce bypasses, special-case validators, duplicate recovery paths, relaxed criteria, ignored mismatches, or threshold changes merely to make a failing check pass;
- temporary diagnostic instrumentation/recovery tooling is allowed only when explicitly non-authoritative and used to establish or repair root cause;
- repeated repair wrappers, duplicated validators, or circular provenance/recovery logic are architectural defects to simplify rather than extend;
- continue through ordinary read-only/reversible work without unnecessary operator stops;
- keep frontend/web code as a client of accepted backend/API contracts;
- treat deployment configuration, service management, persistence, restart behavior, security, logging, and recovery as tested software where applicable.

Operator interaction is reserved for facts that repository/CI cannot establish, genuine product decisions, credentials/provider evidence, real broker mutations, destructive actions, deployment/environment choices requiring user authority, or authority-changing operations.

## 5. Development testing is not acceptance

Focused/unit tests during implementation shorten feedback loops but do **not** mean the phase passed.

Likewise, a script producing output, a provider responding, a backtest producing profit, a paper order submitting, a GUI rendering, a deployment starting, or an AI review completing does not independently accept a phase.

Only the complete phase-end gate accepts the phase.

## 6. Full phase-end acceptance gate

Every phase must run the complete applicable validation stack after phase work is finished. Unless genuinely inapplicable and documented, this includes:

1. syntax/compile/static checks supported by the repository;
2. all phase-focused unit/contract/integration tests;
3. an independent validator or equivalent independent verification;
4. every retained historical validator needed to prove no accepted authority/regression was broken;
5. the complete repository regression test suite;
6. Ubuntu + Windows CI on the exact acceptance head;
7. negative/adversarial/error-path testing appropriate to the phase;
8. restart/idempotency/recovery/reconciliation testing whenever stateful/external operations are involved;
9. target-machine/provider/broker/deployment evidence only when mocks/CI cannot establish the required fact;
10. reproducibility/lineage checks for analytical/research/model results;
11. frontend/API/security/permission tests when GUI/web controls are involved;
12. deployment/startup/shutdown/restart/persistence/logging/rollback checks when deployment work is involved;
13. confirmation that forbidden provider/broker/PAPER/LIVE/support/automation writes remained zero unless explicitly authorized;
14. documented closure of material failures showing root cause was corrected rather than bypassed;
15. synchronization of roadmap, current status, active phase document, README/other living docs where needed.

The exact tested/documented head is the only candidate for acceptance and merge.

## 7. Phase outcomes

### ACCEPTED — POSITIVE

The implementation/evidence passed the full gate and earned the capability/authority explicitly defined by the phase.

### ACCEPTED — NEGATIVE

A preregistered research/question phase passed technically and scientifically but found no acceptable candidate/edge/replacement. This is valid evidence. It grants no authority that depended on a positive result.

### NOT ACCEPTED

Implementation, evidence, validation, CI, target/deployment evidence, recovery, or a mandatory acceptance criterion failed. Root-cause analysis/correction is mandatory in the same phase before acceptance can be reconsidered. Do not create a new phase, alternate acceptance path, weaker test, special-case exemption, or changed scientific threshold merely to avoid repairing the active phase.

## 8. Research-specific rules

Research phases must distinguish feasibility/exploration from confirmation.

- Data feasibility/provenance may be proven before hypothesis freeze only when it inspects no target outcomes and grants no alpha authority.
- Protected/final evidence remains untouched until frozen candidate definitions and acceptance methodology exist.
- Losing alternatives are not revived after protected evidence without a newly declared future research phase.
- Multiple testing, repeated optimization, data snooping, and backtest overfitting are first-class risks.
- Point-in-time populations and chronology are mandatory.
- Costs/market frictions must be appropriate to the instrument/strategy, not selected to make results pass.
- Dependence among overlapping outcomes or same-session observations must not be treated as independent evidence.
- Zero finalists is a valid phase result when produced under the frozen methodology.
- A failed research family is not retuned after results under a different phase label; a later research phase must materially change the information/economic mechanism.

Internal labels such as `work package`, `feasibility`, `checkpoint`, `development split`, `internal validation`, or `protected confirmation` are allowed. Do not create future project progress labels such as `Gate0`, `Gate1`, etc. inside a numbered phase unless an external technical standard requires that term. **The numbered phase is the gate.**

## 9. Provider/broker/mutation authority

Credentials, endpoints, connected accounts, local artifacts, passing tests, rendered UI controls, successful deployments, or prior successful calls never create authority.

Read-only provider work may use a bounded explicit CLI/API command as authorization when the active phase says so. Real mutations, destructive cleanup, PAPER submits, broker switching, order/position changes, and LIVE require the exact authority defined for that operation.

Unknown or uncertain mutation state fails closed. Reconcile before retry. Never blindly retry an ambiguous submit/cancel/replace/close operation.

Automatic cross-broker failover remains forbidden. PAPER never implies LIVE. Frontend controls never bypass these rules.

## 10. Plain-English phase end is mandatory

Every phase completion report must first provide:

1. **Goal**;
2. **What we built**;
3. **Did the full phase gate pass?** — `PASS / ACCEPTED-POSITIVE`, `ACCEPTED-NEGATIVE`, or `NOT ACCEPTED`;
4. **What the results mean**;
5. **What ATLAS can do now** — real capability/authority change or `NONE`;
6. **What is still missing or risky**;
7. **Where this leaves the project**;
8. **What happens next** and why.

When GUI/web/deployment work is involved, also state what the operator can now see/control, where the application is deployed, whether it is development/test/PAPER/production, and what actions remain blocked.

Detailed row counts, fingerprints, hashes, statistical tables, CI IDs, validator outputs, deployment logs, and material failure/root-cause/repair evidence follow as the audit record.

## 11. Current application

- **Accepted foundation through Phase29.**
- Phase28 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` through PR #32.
- Phase29 disposition: `ACCEPTED_NEGATIVE` on accepted closeout head `e078fe56cad4900be54bf39d7d88679d2f6dc4df`.
- Phase29 target/closeout: 14,523 development relative-value rows; 745 protected predictors; zero survivors/winners/finalists/support; zero protected candidate/return reads; inherited holdout unconsumed; independent validation PASS; end-to-end anti-workaround PASS.
- Exact-head workflow `33123195681` passed Ubuntu/Windows, all retained validators, Phase29 closeout contracts, and full regression.
- Phase11 support remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.
- The `2026-05-12` through `2026-08-11` protected predictor window remains genuinely outcome-unopened after Phases26–29.
- **Next project gate: Phase30 — Event-Driven Public-Information Alpha.**
- Phase30 begins with non-performance-bearing historical-news PIT/coverage/provenance feasibility, then freezes a finite hypothesis/acceptance contract before any target outcome inspection.
- Signal-to-trade construction is Phase31 and remains blocked until at least one strategy/alpha candidate earns accepted historical analytical `SUPPORTED` authority.

GUI/web/deployment remains a locked progressive track: contracts/read-only prototype in Phase31, replay/stress dashboard Phase32, SHADOW/PAPER operator web beta Phase33, performance/learning/drift UI Phase34, full production web application/PostgreSQL/scheduler/deployment Phase35, deployment/failure/security/reconciliation hardening Phase36, and controlled LIVE controls Phase37.

Preserve all existing data integrity, execution, risk, AI-independence, broker, browser, scheduler/PostgreSQL, deployment, and LIVE authority boundaries unless a later numbered phase explicitly earns a change.
