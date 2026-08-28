# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md` — normative mission, architecture, acceptance model, and remaining roadmap;
2. `docs/current_status.md` — exact current handoff;
3. active phase spec — `docs/phase32_sec_8k_material_event_alpha.md`;
4. latest accepted closeout — `docs/phase31_closeout.md`;
5. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
6. accepted code, validators, CI/PR evidence.

Historical Phase31 source records remain under `docs/phase31_form4_feasibility_incident.md`, `docs/phase31_form4_source_quality_repair.md`, `docs/phase31_full_historical_acquisition.md`, `docs/phase31_predictor_evidence.md`, and `docs/phase31_scientific_contract.md`.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; do not assume unrelated paid datasets/plans.
- Official SEC EDGAR = read-only authoritative regulatory submission provenance when explicitly phase-gated.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Phase model

One numbered phase is one project acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Legitimate negative science may close `ACCEPTED_NEGATIVE` and does not create missing downstream authority.

## Current state — 2026-08-28

- Accepted foundation: **through Phase31**.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE` alpha phases; supported modern alpha remains **0**.
- Phase31 PR #35 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase31 independent closeout: `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`; zero survivors/winners/finalists/support; zero protected reads; holdout unconsumed.
- Master protected outcome window remains `2026-05-12..2026-08-11` and outcome-unopened for a new frozen finalist-only study.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Current internal target = source feasibility only using Massive `/stocks/filings/vX/index` for original 8-K discovery plus official SEC EDGAR submission headers for exact acceptance timestamps and item labels.
- Feasibility hypotheses are **NOT YET FROZEN** and target/protected market outcomes are forbidden.
- Conservative timing boundary = `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.
- Phase33 signal-to-trade remains blocked until supported alpha exists.
- LIVE remains disabled. Automatic broker failover remains disabled.

Phase31 provenance remains immutable: the original feasibility failure was a **Massive early-access/beta source-association/data-quality defect**; source-quality fingerprint `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`; full acquisition retained 2,993,648 raw / 2,992,608 authoritative rows. Do not retune Form-4 after results.

Historical validator migration note only: the prior roadmap used the exact labels `Active Phase31: SEC Form-4 Insider-Transaction Alpha`, `Phase32 — Signal-to-Trade Construction`, and `Phase38 — Controlled LIVE Activation`. They are preserved as provenance, not current authority.

## Remaining roadmap

- **Phase32:** SEC 8-K Material Corporate-Event Alpha — active feasibility first.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
