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

Internal research splits, checkpoints, development tests, feasibility steps, or protected-evidence steps are not separate project gates. Full regression, retained validators, Ubuntu/Windows CI, negative/recovery testing, independent validation, and target-machine/provider/broker evidence where required happen at the phase-end acceptance boundary.

## Required plain-English communication

At the start of every phase, explain where ATLAS is, what the phase is trying to accomplish, why it matters to the profit/account-growth goal, what will change, what will be tested, what success means, what a legitimate negative means, and what is explicitly not happening yet.

At the end of every phase, explain the goal, what was built, whether the full gate passed, practical meaning, actual new authority/capability or `NONE`, remaining risk/blockers, roadmap position, and exact next objective. Technical hashes/statistics follow as audit evidence; they never replace the operator explanation.

See [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md).

## GUI, web development, and deployment are part of the product

The ATLAS browser/GUI is the intended day-to-day operator experience, but it remains a client of accepted backend authority rather than a second trading engine.

Four consecutive modern alpha phases (26–29) closed as scientifically valid negatives, so the downstream product path remains gated on finding validated alpha. The rebaselined sequence is:

- **Phase30:** event-driven public-information alpha; no major frontend build.
- **Phase31:** signal-to-trade/risk contracts + read-only complete-case web prototype.
- **Phase32:** historical replay/stress dashboard.
- **Phase33:** prospective SHADOW/PAPER operator web beta.
- **Phase34:** outcome/performance/learning/drift dashboards and governance.
- **Phase35:** complete production web application + PostgreSQL operational state + scheduler + deployment engineering.
- **Phase36:** failure/security/reconciliation/deployment hardening; LIVE still disabled.
- **Phase37:** controlled LIVE activation/disable and evidence-based scaling.

Frontend controls call accepted backend/API contracts. The Python trading engine remains the source of analytical, risk, broker, and execution authority.

## Current state — 2026-08-27

- **Accepted foundation through Phase29.**
- Phase28 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` through PR #32; disposition `ACCEPTED_NEGATIVE`.
- Phase29 frozen policy fingerprint: `5d40218c1c554117388d99362ce1343fde8a598aaa6d09b95e83fad7e625b30d`.
- Phase29 target/closeout result: **14,523** development relative-value rows, **745** protected predictors, zero selection survivors, zero winners, zero finalists, zero supported candidates, zero protected candidate/return reads, inherited holdout unconsumed, independent validation PASS, anti-workaround audit PASS.
- Phase29 disposition: **`ACCEPTED_NEGATIVE`**.
- Phase29 accepted closeout head: `e078fe56cad4900be54bf39d7d88679d2f6dc4df`.
- Workflow `33123195681` passed the complete retained stack, Phase29 closeout validator, and full regression on Ubuntu and Windows.
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- The inherited protected predictor window remains `2026-05-12` through `2026-08-11` and is still genuinely outcome-unopened after Phases26–29.
- **Next gate: Phase30 — Event-Driven Public-Information Alpha.**
- Signal-to-trade construction is Phase31 and remains blocked until at least one alpha candidate earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled; automatic broker failover remains disabled.

## Why Phase30 is next

Phase26 rejected deterministic/composite focal self-feature alpha. Phase27 rejected bounded cross-sectional expected-return/ranking models. Phase28 rejected cross-stock residual/lead-lag predictive relationships. Phase29 rejected PCA/nearest-pair relative-value mean-reversion confirmation. All four closed under frozen standards without consuming the protected outcomes.

Phase30 therefore changes the **information source**. It will test event-driven public company information/news rather than another transformation of the same price-derived evidence. Massive's Stocks News API exposes ticker-linked articles with explicit publication timestamps and associated metadata, making historical PIT feasibility worth proving.

Phase30 begins with a non-performance-bearing historical-news feasibility/provenance work package. It must prove coverage, entitlement, chronology, pagination, ticker linkage, deterministic replay, and PIT safety before freezing a finite hypothesis library. No target outcomes may be inspected during feasibility. Provider-derived historical model fields that cannot prove stable PIT semantics must be excluded or replaced with deterministic local transforms of contemporaneously observable text/metadata.

A positive Phase30 result may grant historical analytical support only and unlock Phase31. A negative result is accepted rather than tuned away.

## Remaining planned phases

- **Phase30:** Event-Driven Public-Information Alpha.
- **Phase31:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype.
- **Phase32:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase33:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase34:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase35:** Production Web Application, Operations & Deployment.
- **Phase36:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification.
- **Phase37:** Controlled LIVE Activation & Evidence-Based Scaling through the production control plane.

The full purpose, entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate unavailable history; finalized facts outrank provisional state; unknown/uncertain mutation state fails closed and requires reconciliation; valid trade geometry and portfolio risk are mandatory; community trading ideas are hypotheses that must be tested rather than assumed; the frontend never duplicates or bypasses engine authority; no automatic broker failover; PAPER does not imply LIVE; AI cannot create authority; negative research cannot satisfy a positive downstream gate; and LIVE exists only after the final separately accepted Phase37 authority gate.
