# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/phase32_sec_8k_material_event_alpha.md`;
4. `docs/phase32_semantic_source_qualification.md`;
5. `docs/phase31_closeout.md`;
6. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
7. accepted code, validators, CI/PR evidence.

Retained Phase32 source-incident history is in `docs/phase32_sec_edgar_access_incident.md`.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; unrelated paid datasets/plans are never assumed.
- Official SEC EDGAR = read-only authoritative regulatory submission provenance when explicitly phase-gated.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Operating rule

One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

If an error occurs, ATLAS stops progression, identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. A workaround/different method is considered only after the intended method is shown infeasible. Material decisions and completed gates must be synchronized into the roadmap/status/phase docs/README before the work is considered complete.

## Current state — 2026-08-28

- Accepted foundation: **through Phase31**.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; supported modern alpha remains **0**.
- Phase31 PR #35 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.

### Phase32 core source feasibility

Accepted V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS** with **6,048** Massive original-8-K index rows, **48** reconciled official SEC records, **94** item codes, **0** SEC filing-date mismatches, and **0** target/protected return reads.

Accepted core source = Massive `/stocks/filings/vX/index?form_type=8-K` plus official SEC `data.sec.gov/submissions`. Timing remains `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

### Exact active target — semantic V1 diagnosis

Semantic V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine result: **NOT ACCEPTED**. Failed checks:

- `all_sampled_tickers_align`;
- `all_sampled_supporting_text_is_grounded`.

A contract defect was also found: the V1 January-2022 history assumption was not supported by the supplied Massive endpoint docs and is rejected. V1 is retained as failed source-only evidence; it read zero market outcomes.

Current diagnostic:

`scripts/diagnose_phase32_semantic_failure.py`

Do not modify grounding/ticker rules, freeze hypotheses, or inspect returns until the diagnostic identifies the actual cause.

Phase33 signal-to-trade remains blocked. LIVE and automatic broker failover remain disabled.

## Remaining roadmap

- **Phase32:** SEC 8-K Material Corporate-Event Alpha — active.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
