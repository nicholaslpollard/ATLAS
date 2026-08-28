# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed; trade frequency is never a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Start here — anti-drift continuation order

Every new ATLAS chat/work session must read these in order before changing the system:

1. [`docs/roadmap.md`](docs/roadmap.md) — **normative mission, anti-drift rules, architecture, acceptance model, and remaining roadmap**;
2. [`docs/current_status.md`](docs/current_status.md) — exact repository/current-phase handoff and latest target evidence;
3. active phase specification — currently [`docs/phase31_sec_insider_transaction_alpha.md`](docs/phase31_sec_insider_transaction_alpha.md);
4. any open active-phase incident/repair record — currently [`docs/phase31_form4_feasibility_incident.md`](docs/phase31_form4_feasibility_incident.md);
5. [`docs/phase_flow.md`](docs/phase_flow.md) — phase = acceptance-gate development contract;
6. [`docs/phase_plain_english_contract.md`](docs/phase_plain_english_contract.md) — required operator-facing phase start/end explanation;
7. accepted code, validators, CI/PR evidence, and older phase documents for provenance.

Accepted `main` controls what already exists. The master roadmap controls intended direction. The active phase documents/current status control the work-in-progress handoff. Older documents never silently redefine later accepted authority.

## Locked architecture

`market/reference/regulatory data -> Parquet lake -> DuckDB analytics -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options instrument selection -> entry/exit geometry -> portfolio risk/sizing -> consolidated deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> outcome/performance learning -> browser/web control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive subscription constraint = **Stocks Starter**; do not assume Financials & Ratios Expansion, an Options plan, paid partner data, or unavailable stock trade/quote entitlements.
- Parquet = durable analytical/history lake; DuckDB = analytical engine; PostgreSQL = later operational state after separate promotion.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML = predictive/probability evidence, never unilateral trade authority.
- AI = independent audit/challenge layer, never unilateral authority.
- Browser/web GUI = operator surface, never a second trading engine.

## Phase execution model

Starting with Phase26, the numbered phase itself is the project acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT COHERENT WORK -> FOCUSED DEVELOPMENT TESTS -> COMPLETE FULL PHASE-END ACCEPTANCE GATE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Internal feasibility, acquisition, predictor, development, blindness, or protected-confirmation steps are not separate project gates. Legitimate negative science may close `ACCEPTED_NEGATIVE`; it does not create missing downstream authority.

## Current state — 2026-08-28

- Accepted foundation: **through Phase30**.
- Phases26–30 are all scientifically valid `ACCEPTED_NEGATIVE` alpha phases.
- Phase30 PR #34 merged at `bf673ad82886e7172db0d54a33dd9612fa9ea29e`; post-merge workflow `33141442154` passed Ubuntu and Windows.
- Phase11 strategy authority remains **SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5**.
- Master protected outcome window remains `2026-05-12` through `2026-08-11`; Phases26–30 read zero protected returns and it remains outcome-unopened.
- **Active Phase31: SEC Form-4 Insider-Transaction Alpha.**
- Active branch: `phase-31-sec-insider-transaction-alpha`.
- Massive planning entitlement: **Stocks Starter**.
- Frozen Phase31 feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`.
- First real Phase31 target run at head `b59a64938eb84c0c1e7df3aaea390cc437326f94` reached authenticated Form-4 retrieval but returned **`FEASIBILITY_FAIL`** on `transaction_dates_do_not_postdate_filings`.
- Phase31 is therefore **NOT ACCEPTED** and no alpha hypothesis/support/trading authority was granted.
- Root-cause investigation uses the immutable provider JSONL written by that failed run; the next diagnostic makes zero provider calls and reads zero market outcomes.
- The conservative public-availability rule remains `NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE` and has not been weakened.
- Phase32 signal-to-trade remains blocked until at least one alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled. Automatic broker failover remains disabled.

See [`docs/current_status.md`](docs/current_status.md) and [`docs/phase31_form4_feasibility_incident.md`](docs/phase31_form4_feasibility_incident.md) for exact handoff evidence.

## Remaining roadmap

- **Phase31:** SEC Form-4 Insider-Transaction Alpha — active; feasibility chronology root cause unresolved.
- **Phase32:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase33:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase34:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase35:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase36:** Production Web Application, Operations & Deployment.
- **Phase37:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase38:** Controlled LIVE Activation & Evidence-Based Scaling.

Full entry conditions, acceptance boundaries, web/deployment responsibilities, and conditional progression rules are defined only in [`docs/roadmap.md`](docs/roadmap.md).

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after seeing results; never use a frontend to bypass engine authority; never auto-failover brokers; PAPER does not imply LIVE; protected performance is finalist-only; and LIVE exists only after the final separately accepted authority gate.
