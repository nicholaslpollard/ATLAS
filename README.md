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

After the accepted-negative Phase26–28 alpha results, an additional materially different alpha gate became necessary before downstream trade construction can legitimately begin. The current progressive sequence is:

- **Phase29:** relative-value/statistical-arbitrage alpha confirmation; no major frontend build.
- **Phase30:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase31:** historical replay/stress dashboard.
- **Phase32:** prospective SHADOW/PAPER operator web beta.
- **Phase33:** outcome/performance/learning/drift dashboards and governance.
- **Phase34:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase35:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase36:** controlled LIVE activation/disable and evidence-based scaling.

Frontend controls call accepted backend/API contracts. The Python trading engine remains the source of analytical, risk, broker, and execution authority.

## Current state — 2026-08-27

- **Phases 1–28: ACCEPTED / MERGED.**
- Phase28 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` through PR #32.
- Phase28 disposition: **ACCEPTED_NEGATIVE**.
- Phase28 target result: 14,466 development network rows, 741 protected predictors, zero selection survivors, zero winners, zero finalists, zero supported candidates, zero protected candidate/return reads, inherited holdout unconsumed, independent validation PASS, anti-workaround audit PASS.
- Phase28 post-merge workflow `33114372397` passed the complete retained stack and full regression on Ubuntu and Windows.
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- **Current gate: Phase29 — Relative-Value Statistical-Arbitrage Confirmation Alpha.**
- Phase29 is preregistered and implemented through the pre-target hardening boundary; no Phase29 performance has yet been accepted or used to change the frozen research contract.
- The inherited protected predictor window remains `2026-05-12` through `2026-08-11` and remains outcome-unopened until the frozen finalist-only protected path legitimately requires a read.
- Phase30 remains blocked unless Phase29 produces at least one accepted historical analytical `SUPPORTED` candidate.
- LIVE remains disabled; automatic broker failover remains disabled.

## Why Phase29 is the priority

Phase26 rejected preregistered deterministic/composite focal self-feature alpha. Phase27 rejected bounded cross-sectional expected-return/ranking models. Phase28 rejected cross-stock residual/lead-lag predictive relationships. All three closed under frozen modern standards without consuming the inherited protected outcomes.

The next scientific step therefore changes the economic mechanism rather than retuning a failed family. Phase29 tests exactly four preregistered relative-value mean-reversion hypotheses: PCA residual reversion and nearest normalized-price-path pair reversion, independently LONG and SHORT. Formation windows, signal tails, focal-stock t+3 outcomes, economics, chronological selection/internal validation, dependence treatment, robustness requirements, global Holm correction, and finalist-only protected confirmation are frozen before performance.

Phase29 creates no broker/PAPER/LIVE authority and does not claim ATLAS supports market-neutral pair execution. If no candidate earns support, the negative result is accepted rather than tuned away and Phase30 remains blocked.

## Remaining planned phases

- **Phase29:** Relative-Value Statistical-Arbitrage Confirmation Alpha.
- **Phase30:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype.
- **Phase31:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase32:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase33:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase34:** Production Web Application, Operations & Deployment.
- **Phase35:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification.
- **Phase36:** Controlled LIVE Activation & Evidence-Based Scaling through the production control plane.

The full purpose, entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate unavailable history; finalized facts outrank provisional state; unknown/uncertain mutation state fails closed and requires reconciliation; valid trade geometry and portfolio risk are mandatory; community trading ideas are hypotheses that must be tested rather than assumed; the frontend never duplicates or bypasses engine authority; no automatic broker failover; PAPER does not imply LIVE; AI cannot create authority; and LIVE exists only after the final separately accepted Phase36 authority gate.
