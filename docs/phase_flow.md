# ATLAS Phase Execution Flow

**Normative phase-as-gate development contract. Re-baselined: 2026-08-30 after Phase32 merge, accepted XBRL source feasibility, and opening the frozen XBRL source-only PIT chronology/restatement/identity audit.**

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

A later mechanism may reuse accepted source infrastructure or a source-only issuer inventory without inheriting prior candidate/performance authority. Reused lineage must be explicit and limited to the exact non-performance facts required.

A current aggregate regulatory API is not automatically a historical point-in-time dataset. When exact accession and authoritative publication/acceptance metadata exist, ATLAS must version facts by accession and reconstruct availability from that chronology rather than allow later restatements or comparative values to overwrite earlier state.

## Provider/broker/mutation authority

Credentials, endpoints, local artifacts, passing tests, rendered controls, or prior successful calls never create authority. Read-only provider work must be explicitly phase-gated. Unknown mutation state fails closed. PAPER never implies LIVE. Automatic cross-broker failover remains forbidden.

## Current application

- Accepted project foundation: **through Phase32**, merged into `main` at `69f8aa81289934b71f2652482c747391917c15a3` via PR #37.
- Phases26–32 are `ACCEPTED_NEGATIVE`; accepted historical modern alpha remains **0**.
- Phase32 development produced one frozen finalist, `solvency_distress_short`; the independent finalist blindness/lineage audit proved its protected source-only population was **46 event rows / 33 signal sessions / 40 unique instruments** versus the frozen **50 / 20 / 20** minimum.
- Protected returns remain unread. Phase32 protected return rows read = 0; holdout consumed = false.
- Phase33 Signal-to-Trade Construction remains blocked because accepted historical `SUPPORTED` alpha remains zero.
- The materially different SEC XBRL fundamental-quality/accrual mechanism remains pre-Phase33 research and grants no downstream authority.
- Its source-only feasibility contract `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes` returned **`FEASIBILITY_PASS`** on target-machine head `5a8c15f95417390d0d64ff240977adfb38a20c45`.
- Retained feasibility fingerprint: `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`.
- Accepted feasibility evidence: **200** successful Company Facts documents, **170** accrual-history-ready issuers, **92** profitability-history-ready issuers, zero target outcomes, zero protected returns, and an unconsumed holdout.
- Accepted feasibility evidence fingerprint: `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`.
- The current pre-Phase33 gate is the frozen **SEC XBRL PIT source/chronology/restatement/identity audit** on branch `alpha-gate-sec-xbrl-fundamental-quality-pit-audit`.
- Current PIT audit fingerprint: `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`.
- Exactly 40 feasibility-ready issuer CIKs are deterministically sampled; up to 5 evenly spaced original 10-Q/10-K accessions per issuer are audited.
- Exact SEC accession/form/date/acceptance time controls chronology; later accession versions never overwrite earlier facts.
- Massive issuer-to-instrument mapping uses exact CIK + point-in-time date and the accepted `instrument-identity-v4-no-issuer-level-medium-collapse` contract; zero or multiple eligible instruments fail closed.
- Alpha hypotheses are **not yet frozen**. Market prices/returns, target outcomes, and protected returns are **forbidden / unread**.
- An `AUDIT_PASS` can authorize only the next finite hypothesis/outcome/cost/statistical/protected-policy freeze before any market outcome is opened.
- LIVE remains disabled and automatic broker failover remains disabled.
