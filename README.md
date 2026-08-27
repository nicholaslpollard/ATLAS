# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its end goal is to use trustworthy market evidence, validated quantitative edge, disciplined risk management, appropriate stock/options trade construction, reliable execution, and outcome learning to make educated trades with the objective of growing account equity and producing profit over time after realistic costs. Profit is never guaranteed; the system is designed to maximize decision quality and risk-adjusted expected account growth rather than trade frequency.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after separate acceptance, controlled LIVE operation.

## Start here — anti-drift order

Future ATLAS chats/work should read these in order before changing the system:

1. [`docs/roadmap.md`](docs/roadmap.md) — **normative mission, anti-drift rules, GUI/web/deployment path, and complete remaining roadmap**;
2. [`docs/current_status.md`](docs/current_status.md) — exact repository/current-phase handoff;
3. active phase specification — frozen scope/evidence/authority for the current phase;
4. [`docs/phase_flow.md`](docs/phase_flow.md) — **phase = acceptance gate** development contract;
5. [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md) — required plain-English phase-start and phase-end explanation;
6. accepted code, validators, CI/PR evidence, and older phase documents for detailed provenance.

Accepted `main` controls what already exists. The master roadmap controls the intended destination and future sequence. Older phase documents never silently redefine either.

## Architecture

`market/reference data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> candidate promotion -> analogue/scenario/news research -> stock/options instrument selection -> entry/exit/geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome/performance learning -> browser/web control plane -> production deployment/operations`

Massive is primary market/reference. Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance. Alpaca is manual secondary only. ML is predictive/probability evidence, AI is an independent audit, and the browser/web application is the operator control surface rather than a parallel trading engine.

## Phase execution model

Starting with Phase26, **the numbered phase itself is the project gate**.

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK PHASE -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTING -> FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT/REPAIR -> MERGE -> NEXT PHASE`

Internal research splits, checkpoints, development tests, or protected-evidence steps are not separate project gates. Full regression, retained validators, Ubuntu/Windows CI, negative/recovery testing, independent validation, and target-machine/provider/broker evidence where required happen at the phase-end acceptance boundary.

## Required plain-English communication

The operator should never have to interpret raw technical logs to understand where ATLAS stands.

At the **start of every phase**, explain in ordinary language:

- where the project is now;
- what the phase is trying to accomplish;
- why it matters to the profit/account-growth end goal;
- what will actually be built or changed;
- what will be tested at the end;
- what success means;
- what happens if the phase fails or produces a negative result;
- what is explicitly not happening yet.

At the **end of every phase**, explain before technical evidence:

- the goal;
- what was built;
- whether the full phase gate passed;
- what the results mean in practical terms;
- what ATLAS can do now that it could not do before, or `NONE`;
- what is still missing/risky;
- where the project now sits in the roadmap;
- exactly what happens next and why.

Hashes, p-values, fingerprints, row counts, test logs, and CI IDs may still follow when useful for auditability and continuation, but they never replace the plain-English explanation. See [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md).

## GUI, web development, and deployment are part of the product

The ATLAS browser/GUI is not a cosmetic afterthought. It is the intended day-to-day operator experience and is built progressively without duplicating trading logic in the frontend.

After the Phase26 accepted-negative alpha result, the downstream product phases moved one number later so the failed alpha entry condition is not silently skipped:

- **Phase27:** cross-sectional expected-return/ranking alpha research; no major frontend build.
- **Phase28:** stabilize trade/case/risk outputs into web-facing contracts and begin read-only interface prototypes.
- **Phase29:** historical replay/stress dashboard views.
- **Phase30:** SHADOW/PAPER operator web beta for runs, cases, AI review, paper orders/positions, alerts, failures, and reconciliation. No LIVE authority.
- **Phase31:** outcome, performance, calibration, strategy/regime, drift, and learning dashboards.
- **Phase32:** complete production web application, operational state, scheduler, host/service packaging, secure configuration, deployment, restart/recovery, logging, backups, and deployment documentation.
- **Phase33:** deployed-stack outage/restart/stale-data/broker-provider/reconciliation/emergency hardening. LIVE still disabled.
- **Phase34:** controlled LIVE activation/disable, risk-envelope visibility, reconciliation/health, and evidence-based scaling through backend-authorized GUI controls.

Frontend controls call accepted backend/API contracts. The Python trading engine remains the source of analytical, risk, broker, and execution authority.

## Current state — 2026-08-27

- **Phases 1–26: ACCEPTED / MERGED.**
- Phase26 merge: `2074808605cf85b5462e5999ed1836d68b0434c3` through PR #30.
- Phase26 disposition: **ACCEPTED_NEGATIVE**.
- Phase26 target result: 21,483 development observations, zero selection survivors, zero finalists, zero supported candidates, zero protected-return reads, independent validation PASS.
- Phase26 end-to-end anti-workaround audit: PASS.
- Phase26 merge-head CI `33075333287` passed Ubuntu/Windows after merge.
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- **Current gate: Phase27 — Cross-Sectional Expected-Return Learning & Ranking.**
- LIVE remains disabled; automatic broker failover remains disabled.

## Why Phase27 is the priority

Phase24 showed bounded variants of the original strategy families were not robust. Phase25 showed the production-path population mismatch was not hiding incumbent edge. Phase26 then tested 24 materially different hand-designed deterministic/composite candidates and still produced zero selection survivors under frozen, dependence-aware, after-cost methodology.

The next scientific step is therefore not another threshold sweep. Phase27 tests whether the production-path-native feature set contains **continuous cross-sectional expected-return/ranking information** that finite preregistered statistical/ML models can learn and convert into robust after-cost long/short edge. Simple regularized baselines, bounded nonlinear tree-based prediction, and bounded ranking methods must compete under chronological walk-forward validation, dependence/multiplicity controls, and untouched protected confirmation.

Phase27 creates no broker/PAPER/LIVE authority. If no model earns support, downstream Phase28 remains blocked and the negative result is accepted rather than tuned away.

## Remaining planned phases

- **Phase27:** Cross-Sectional Expected-Return Learning & Ranking.
- **Phase28:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype.
- **Phase29:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase30:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase31:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase32:** Production Web Application, Operations & Deployment.
- **Phase33:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification.
- **Phase34:** Controlled LIVE Activation & Evidence-Based Scaling through the production control plane.

The full purpose, entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate unavailable history; finalized facts outrank provisional state; unknown/uncertain mutation state fails closed and requires reconciliation; valid trade geometry and portfolio risk are mandatory; community trading ideas are hypotheses that must be tested rather than assumed; the frontend never duplicates or bypasses engine authority; no automatic broker failover; PAPER does not imply LIVE; AI cannot create authority; and LIVE exists only after the final separately accepted Phase34 authority gate.
