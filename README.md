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

The planned track is:

- **Phase26:** alpha work remains the critical path; only UI/API data-contract needs are identified where useful so research is not displaced by frontend work.
- **Phase27:** stabilize trade/case/risk outputs into web-facing contracts and begin read-only interface prototypes for candidate/trade-plan inspection.
- **Phase28:** add historical replay/stress-result dashboard views so full-system behavior can be inspected visually.
- **Phase29:** operate a SHADOW/PAPER web beta for run status, candidates, cases, AI review, paper orders/positions, alerts, failures, and reconciliation. No LIVE authority.
- **Phase30:** add outcome, performance, calibration, strategy/regime, drift, and learning dashboards.
- **Phase31:** build/consolidate the full production web application, operational controls, authentication/security boundaries as applicable, PostgreSQL operational-state promotion, scheduler integration, host/service packaging, configuration, deployment, restart/recovery, logging, backups, and deployment documentation.
- **Phase32:** harden the deployed application under outages, process restarts, stale data, broker/provider failures, reconciliation faults, and emergency controls.
- **Phase33:** expose controlled LIVE activation/disable, risk-envelope visibility, reconciliation/health, and evidence-based scaling controls through the production GUI without allowing the GUI to bypass engine authority.

Frontend controls call accepted backend/API contracts. The Python trading engine remains the source of analytical, risk, broker, and execution authority.

## Current state — 2026-08-26

- **Phases 1–25: ACCEPTED / MERGED.**
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase25 target code head `302bf6db5d807884f3b74cda049fc95864c5a194`; CI `32981080421` passed Ubuntu/Windows.
- Phase25 final docs head `f2d10465b71446b253b5d73a50845d2ea1e704d3`; CI `33025699177` passed Ubuntu/Windows.
- Phase25 result: **NO SUPPORT REPLACEMENT — DEVELOPMENT ROBUSTNESS FAILED.**
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- **Current next gate: Phase26 — Production-Path-Native Alpha Discovery & Validation.**
- LIVE remains disabled; automatic broker failover remains disabled.

## Why Phase26 is the priority

Phase23 proved the current analytical chain can advance finalized sessions, but zero strategies had SUPPORTED authority. Phase24 tested 28 bounded challenger variants and found no robust replacement. Phase25 reconstructed the true historical production path and showed the old population mismatch was not hiding robust incumbent edge.

Therefore the current bottleneck is **validated alpha**, not another round of infrastructure work. Phase26 researches materially different production-path-native architectures and performs the independent validation/protected confirmation required for any support replacement. It does not grant broker/PAPER/LIVE authority.

If Phase26 produces no supported strategy, downstream LIVE progression stops and the next work remains alpha research based on documented failure modes rather than weaker thresholds.

## Remaining planned phases

- **Phase26:** Production-Path-Native Alpha Discovery & Validation.
- **Phase27:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype.
- **Phase28:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase29:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase30:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase31:** Production Web Application, Operations & Deployment.
- **Phase32:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification.
- **Phase33:** Controlled LIVE Activation & Evidence-Based Scaling through the production control plane.

The full purpose, entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate unavailable history; finalized facts outrank provisional state; unknown/uncertain mutation state fails closed and requires reconciliation; valid trade geometry and portfolio risk are mandatory; community trading ideas are hypotheses that must be tested rather than assumed; the frontend never duplicates or bypasses engine authority; no automatic broker failover; PAPER does not imply LIVE; AI cannot create authority; and LIVE exists only after the final separately accepted phase.