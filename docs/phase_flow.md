# ATLAS Phase Execution Flow

**Normative phase-as-gate development contract. Re-baselined: 2026-08-30 after Phase32, SEC XBRL, SEC Schedule 13D/13G beneficial ownership, and FINRA consolidated short-interest v1 accepted-negative closeouts.**

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

A frozen source-only scientific gate may close `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT` when its preregistered protected sample requirements cannot be met and market outcomes remain unread. This is an accepted negative source-capacity result, not a performance result.

## Research rules

Feasibility is not confirmation. Protected evidence remains untouched until candidate definitions and acceptance methodology are frozen. Repeated optimization and data snooping are first-class risks. PIT populations/identity and chronology are mandatory. Costs/frictions cannot be selected to make a result pass. Dependence among overlapping outcomes must be treated explicitly. Zero finalists is valid. A failed research family may not be retuned under a new phase label; the next phase must materially change the mechanism.

A protected source-only impossibility proof is a valid negative closeout path. When a frozen candidate/finalist cannot satisfy a preregistered sample gate from source-only counts, do not spend development or protected market outcomes merely to observe returns that cannot produce an admissible PASS.

If multiplicity was frozen across a finite hypothesis family, a source-only failure in one member cannot be repaired after observation by silently dropping that member and relabeling the experiment. A smaller or otherwise changed family is a new scientific version and must be preregistered before outcomes.

A development-negative result is also a valid closeout path. When zero candidates survive the frozen development hard gates plus multiplicity correction, do not compute internal validation for non-winners, substitute runners-up, alter the hypothesis family, or open protected performance.

A later mechanism may reuse accepted source infrastructure or a source-only issuer/instrument inventory without inheriting prior candidate/performance authority. Reused lineage must be explicit and limited to the exact non-performance facts required.

A current aggregate regulatory API is not automatically a historical point-in-time dataset. When exact accession and authoritative publication/acceptance metadata exist, ATLAS must version facts by accession and reconstruct availability from that chronology rather than allow later restatements or comparative values to overwrite earlier state.

## Provider/broker/mutation authority

Credentials, endpoints, local artifacts, passing tests, rendered controls, or prior successful calls never create authority. Read-only provider work must be explicitly phase-gated. Unknown mutation state fails closed. PAPER never implies LIVE. Automatic cross-broker failover remains forbidden.

## Current application

- Accepted numbered project foundation: **through Phase32**, merged into `main` at `69f8aa81289934b71f2652482c747391917c15a3` via PR #37.
- Phases26–32 are `ACCEPTED_NEGATIVE`; accepted historical modern alpha remains **0**.
- Phase32 protected source-only evidence was **46 event rows / 33 signal sessions / 40 unique instruments** against **50 / 20 / 20**; protected returns remained unread.
- SEC XBRL fundamental-quality/accrual closed `ACCEPTED_NEGATIVE`, merge `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`, closeout fingerprint `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`.
- SEC Schedule 13D/13G beneficial ownership closed `ACCEPTED_NEGATIVE`, merge `208529c5562920cc0b2bcf2bae546e2b9af0a25b`, closeout fingerprint `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`.
- FINRA short-interest source feasibility passed on 12 frozen anchors; PIT audit passed with **136,731 immutable exchange-listed rows**, **63,761 PIT-eligible rows**, and **8,054 unique PIT instruments**.
- FINRA scientific fingerprint: `0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`.
- The full FINRA predictor reconstruction processed **116 source files / 232 Massive PIT snapshots** and produced **19,343** rows: **14,841 DEVELOPMENT / 4,502 PROTECTED**.
- Three frozen FINRA hypotheses passed every source-count gate. `rapid_short_cover_crowded_long` had **257 protected rows versus 300 required**, while **26 versus 16 sessions** and **211 versus 200 instruments** passed.
- FINRA source disposition: `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`.
- FINRA accepted probe evidence fingerprint: `c624da82b45fb8d530c2400262598f266ec6309e614a0dcd135b38d9ba5518ce`.
- FINRA accepted closeout evidence fingerprint: `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.
- FINRA development/target outcome rows read = **0**; protected return rows read = **0**; holdout consumed = **false**.
- The exact FINRA four-hypothesis v1 family is permanently closed to post-result pruning or threshold/multiplicity retuning.
- Master protected window `2026-05-12..2026-08-11` remains unconsumed.
- Phase33 Signal-to-Trade Construction remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- The next alpha family must use a materially different economic/information mechanism.
- LIVE remains disabled and automatic broker failover remains disabled.
