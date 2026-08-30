# ATLAS Phase Execution Flow

**Normative phase-as-gate development contract. Re-baselined: 2026-08-30 after Phase32 merge, accepted-negative SEC XBRL closeout/merge, and accepted-negative SEC Schedule 13D/13G beneficial-ownership development/closeout.**

Read `docs/roadmap.md` first. One numbered phase is one acceptance gate; pre-phase alpha research gates must obey the same scientific/authority discipline.

## Core lifecycle

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT THE COHERENT PHASE PACKAGE -> FOCUSED PHASE TEST -> ROOT-CAUSE TARGETED FIXES IF NEEDED -> RERUN PHASE TEST -> PHASE-END ACCEPTANCE/REGRESSION -> DOCUMENT -> MERGE -> NEXT PHASE`

A failed check is evidence, not an obstacle to route around. Root cause must be corrected at the owning layer. Do not weaken validators, thresholds, chronology, identity, multiplicity, protected-evidence rules, or authority boundaries to convert a failure into PASS. Workarounds that bypass a failed requirement are forbidden.

## Cadence

ATLAS uses a **single coherent acceptance cycle per phase**, not a chain of conversational micro-gates. Implement the largest safe phase package, run the phase-focused test suite, repair only demonstrated root causes, rerun the focused suite, and then perform the consolidated phase-end regression/documentation/CI check before merge and progression.

Intermediate scientific or authority boundaries are permitted only when they are genuinely irreversible or necessary to prevent contamination—for example, freezing a research policy before opening market outcomes, protected evidence access, broker mutation, destructive migration, PAPER authority, or LIVE authority. They are not separate implementation phases and should not create repeated operator checkpoints.

Historical validators, cross-platform parity, living-document synchronization, and full retained regression should normally be consolidated at phase end. If an older retained validator fails only because living-document navigation or wording advanced, record it for the phase-end targeted-fix batch unless it indicates actual scientific, lineage, provider, broker, data-integrity, or authority drift.

Operator interaction is reserved for target-machine/provider/broker/deployment facts repository CI cannot establish, destructive or authority-changing actions, or genuinely ambiguous requirements. A target-machine checkpoint should produce enough evidence to complete the largest possible next repository unit.

## Define / lock

Before material implementation or governed target-performance inspection, state purpose, entry evidence, scope/non-scope, allowed/forbidden authority, authoritative sources, deliverables, success/failure semantics, and the complete phase-end gate.

For research phases, freeze hypotheses/search space, outcomes, chronology, costs, dependence, multiplicity/selection-bias treatment, robustness, concentration, winner/finalist rules, and protected evidence **before** governed performance is opened.

A non-performance data feasibility/provenance step may precede hypothesis freeze only when it reads zero target outcomes, ranks no alpha ideas by performance, and grants no alpha authority.

## Development is not acceptance

A script running, provider responding, backtest profiting, paper order submitting, GUI rendering, or focused test passing is not phase acceptance. The focused phase test authorizes continuation within the already-defined phase scope; only the consolidated phase-end acceptance can close and merge the phase.

## Full phase-end gate

As applicable, require syntax/compile, phase-focused unit/contract/integration tests, independent verification, retained historical validators, full regression, Ubuntu + Windows CI on the exact head, adversarial/error-path checks, reproducibility/lineage, restart/reconciliation for stateful work, target-machine evidence where mocks cannot establish facts, zero forbidden authority, documented root-cause closure, and synchronized living docs. These should be executed as one consolidated closeout package rather than many sequential mini-gates.

## Outcomes

- `ACCEPTED` positive: the phase earned exactly the capability/authority defined by its contract.
- `ACCEPTED_NEGATIVE`: the research executed validly but found no acceptable edge/replacement; no missing downstream authority is granted.
- `NOT ACCEPTED`: a mandatory implementation/evidence/validation criterion failed; repair in the same phase, not through a weaker alternate path.

A pre-performance feasibility gate may separately report `FEASIBILITY_PASS` or `FEASIBILITY_FAIL`; either result grants **no alpha support**. A feasibility PASS authorizes only the next explicitly defined source/scientific work inside the research program.

A source/chronology audit may separately report `AUDIT_PASS` or `AUDIT_FAIL`; either result still grants **no alpha support**. An AUDIT_PASS may authorize only the next explicitly frozen scientific contract before outcomes.

## Research rules

Feasibility is not confirmation. Protected evidence remains untouched until candidate definitions and acceptance methodology are frozen. Repeated optimization and data snooping are first-class risks. PIT populations/identity and chronology are mandatory. Costs/frictions cannot be selected to make a result pass. Dependence among overlapping outcomes must be treated explicitly. Zero finalists is valid. A failed research family may not be retuned under a new phase label; the next phase must materially change the mechanism.

A protected source-only impossibility proof is a valid negative closeout path. When a frozen finalist cannot satisfy a preregistered sample gate from source-only counts, do not spend the holdout merely to observe returns that cannot produce an admissible PASS.

A development-negative result is also a valid closeout path. When zero candidates survive the frozen development hard gates plus multiplicity correction, do not compute internal validation for non-winners, substitute runners-up, alter the hypothesis family, or open protected performance.

A later mechanism may reuse accepted source infrastructure or a source-only issuer inventory without inheriting prior candidate/performance authority. Reused lineage must be explicit and limited to the exact non-performance facts required.

A current aggregate regulatory API is not automatically a historical point-in-time dataset. When exact accession and authoritative publication/acceptance metadata exist, ATLAS must version facts by accession and reconstruct availability from that chronology rather than allow later restatements or comparative values to overwrite earlier state.

## Provider/broker/mutation authority

Credentials, endpoints, local artifacts, passing tests, rendered controls, or prior successful calls never create authority. Read-only provider work must be explicitly phase-gated. Unknown mutation state fails closed. PAPER never implies LIVE. Automatic cross-broker failover remains forbidden.

## Current application

- Accepted project foundation: **through Phase32**, merged into `main` at `69f8aa81289934b71f2652482c747391917c15a3` via PR #37.
- Phases26–32 are `ACCEPTED_NEGATIVE`; accepted historical modern alpha remains **0**.
- Phase32 development produced one frozen finalist, `solvency_distress_short`; its source-only protected population was **46 event rows / 33 signal sessions / 40 unique instruments** versus the frozen **50 / 20 / 20** minimum.
- Phase32 protected return rows read = 0; holdout consumed = false.
- The materially different SEC XBRL fundamental-quality/accrual research program closed **`ACCEPTED_NEGATIVE`** and merged via PR #38 at `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`; post-merge full regression passed on Ubuntu and Windows.
- XBRL feasibility contract `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes` returned `FEASIBILITY_PASS` with 200 successful Company Facts documents, 170 accrual-history-ready issuers, and 92 profitability-history-ready issuers.
- XBRL PIT v1 audit failure is preserved: 139 unambiguous mappings / 28 issuers with >=3 mappings.
- Targeted common-stock active-only identity repair fingerprint `e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f` passed with 171 mappings / 38 issuers and no threshold changes.
- Frozen XBRL scientific fingerprint: `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`.
- Accepted development head: `58e7c9b60ba59d250a7c91e282daefa4aef3c2b9`.
- Accepted XBRL development result: `ACCEPTED_NEGATIVE_DEVELOPMENT` with **5,536** predictors, **3,963** usable development outcomes, **0 selection passers**, **0 winners**, and **0 internal finalists**.
- Accepted XBRL closeout evidence fingerprint: `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- XBRL protected return rows read = **0**; protected holdout consumed = **false**.
- Retained beneficial-ownership source-feasibility mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.
- Retained beneficial-ownership source-only feasibility fingerprint: `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.
- Beneficial-ownership targeted source repair passed before outcomes with 43/43 SEC quarterly indexes, 200/200 complete submissions, 195 unique authoritative subject CIKs, 200/200 decision sessions, and 142 unambiguous PIT active common-stock mappings.
- Beneficial-ownership frozen scientific mechanism: `PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.
- Beneficial-ownership scientific fingerprint: `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`.
- The earlier 3500/5200 predictor transport failure remains preserved as pre-outcome evidence; the valid source cache was retained and the narrow 256 MB scientific submission ceiling repair changed no science.
- Accepted beneficial-ownership development head: `067dc13429c22dc4e789959f56644423f0947946`.
- Repaired beneficial-ownership source-only reconstruction passed with **3,652 predictors**: **2,763 development** and **889 protected-source-only** rows, with zero market-outcome rows read before development opened.
- Accepted beneficial-ownership development result: `ACCEPTED_NEGATIVE_DEVELOPMENT` with **2,412** usable development outcomes, **0 selection passers**, **0 winners**, **0 internal finalists**, and **0 protected-return eligible finalists**.
- Accepted beneficial-ownership closeout evidence fingerprint: `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- Beneficial-ownership protected return rows read = **0**; protected holdout consumed = **false**.
- The beneficial-ownership family is closed `ACCEPTED_NEGATIVE`; post-result ownership-threshold, form/amendment, direction, taxonomy/filter, horizon, cost, sample, multiplicity, winner/finalist, or protected-policy retuning is forbidden.
- Master protected window `2026-05-12..2026-08-11` remains unconsumed.
- Phase33 Signal-to-Trade Construction remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- The next alpha family must use a materially different economic/information mechanism; accepted-negative beneficial-ownership performance cannot be repackaged as support.
- LIVE remains disabled and automatic broker failover remains disabled.
