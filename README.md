# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/phase32_sec_8k_material_event_alpha.md`;
4. `docs/phase32_scientific_contract.md`;
5. `docs/phase32_semantic_source_qualification.md`;
6. `docs/phase31_closeout.md`;
7. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
8. accepted code, validators, CI/PR evidence.

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

If an error occurs, ATLAS stops progression, identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. Material decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

## Current state — 2026-08-29

- Accepted foundation: **through Phase31**.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; supported modern alpha remains **0**.
- Phase31 PR #35 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.

### Retained Phase31 feasibility provenance — historical only

This block preserves the accepted Phase31-era handoff required by retained validators; it does not change the current active Phase32 state.

- **Active Phase31: SEC Form-4 Insider-Transaction Alpha** was the historical active gate.
- The source-quality repair handoff is retained in `docs/phase31_form4_source_quality_repair.md`.
- Repair fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`.
- Historical root cause: **Massive early-access/beta source-association/data-quality defect**.
- The Phase31-era downstream roadmap extended through **Phase38**; later rebaselining moved controlled LIVE activation to current Phase39.

### Accepted Phase32 source stack

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Accepted core source = Massive original-8-K discovery plus official SEC `data.sec.gov/submissions`, with exact accession/CIK/form/date/acceptance reconciliation and zero target/protected return reads.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 passed with taxonomy version 1.0 / 119 rows, 7,468 disclosure rows across five retained probe windows, exact original-8-K accession overlap, 30 Massive Text samples, 30 official SEC reconciliations, and zero target/protected outcome reads.

The source/taxonomy census then passed with 119 taxonomy rows, 112 observed taxonomy rows, 7,468 disclosures, 4,427 unique accessions, 3,097 unique CIKs, 6,231 mapped ticker rows, 1,237 unmapped rows, and zero target/protected outcomes.

### Frozen Phase32 scientific policy

Corrected policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The earlier proposed `0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88` fingerprint was superseded before acceptance and before any market-outcome read after a pre-performance audit corrected its medium-identity semantics.

Exactly **five hypotheses** are frozen before performance:

- `equity_issuance_short`;
- `share_repurchase_long`;
- `financial_integrity_adverse_short`;
- `listing_distress_short`;
- `solvency_distress_short`.

Frozen methodology includes first XNYS regular open strictly after official SEC `acceptanceDateTime`, decision-open entry, five-session close exit, SPY-relative primary plus required unhedged profitability, 10-bps primary / 25-bps stress costs, five-session purge/block bootstrap, mandatory sample/concentration gates, global `HOLM_BONFERRONI_GLOBAL_5`, no runner-up substitution, and finalist-only protected returns.

PIT instrument identity is bound to `instrument-identity-v4-no-issuer-level-medium-collapse`: strong = Composite FIGI / Share Class FIGI; medium = CIK + exact provider-native ticker + primary exchange + security type. Only strong/medium identity is eligible; exactly one filing-CIK-matching instrument must resolve. Ticker+snapshot fallback, current-universe backprojection, and ticker alias backfill are forbidden.

Phase32 market outcomes remain unread.

### Exact active target — full-history source/predictor acquisition

Build and validate **full-history** Phase32 predictor/source evidence for `2021-08-16..2026-08-11` under the corrected frozen fingerprint. This must reconcile original 8-K discovery, semantic disclosure taxonomy, official SEC acceptance metadata, accession/CIK provenance, and point-in-time identity-v4 instrument mapping while reading zero stock/SPY/options outcomes.

A target-machine acquisition run stopped at joint-filer accession `0000034903-25-000028` before any return read. Official SEC evidence confirms multiple filing entities legitimately share that accession. The corrected acquisition now requires at least one original-8-K index row matching the semantic disclosure issuer CIK, preserves other index CIKs as co-filer provenance, and permits only issuer-CIK-matching index rows to contribute ticker mappings. A genuinely absent issuer-CIK match still fails closed. The frozen scientific fingerprint and all outcome/protected rules are unchanged.

Only after that source/predictor gate passes may development returns be opened under the unchanged contract.

Phase33 remains blocked. LIVE and automatic broker failover remain disabled.

## Remaining roadmap

- **Phase32:** SEC 8-K Material Corporate-Event Alpha — active; frozen policy, full-history predictor acquisition next.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
