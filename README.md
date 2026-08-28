# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md` — normative mission, architecture, acceptance model, and remaining roadmap;
2. `docs/current_status.md` — exact current handoff;
3. active phase spec — `docs/phase31_sec_insider_transaction_alpha.md`;
4. Phase31 source/provenance records — `docs/phase31_form4_feasibility_incident.md`, `docs/phase31_form4_source_quality_repair.md`, `docs/phase31_full_historical_acquisition.md`;
5. frozen predictor evidence — `docs/phase31_predictor_evidence.md`;
6. frozen scientific contract — `docs/phase31_scientific_contract.md`;
7. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
8. accepted code, validators, CI/PR evidence.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; do not assume unrelated paid datasets/plans.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Phase model

One numbered phase is one project acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Internal feasibility, acquisition, predictor, development, blindness, and protected-confirmation work are not separate numbered gates. Legitimate negative science may close `ACCEPTED_NEGATIVE` and does not create missing downstream authority.

## Current state — 2026-08-28

- Accepted foundation: **through Phase30**.
- Phases26–30 are scientifically valid `ACCEPTED_NEGATIVE` alpha phases.
- Phase30 PR #34 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`; post-merge workflow `33141442154` passed Ubuntu/Windows.
- Phase11 strategy authority remains SUPPORTED 0 / MIXED 3 / UNSUPPORTED 5.
- Master protected outcome window remains `2026-05-12..2026-08-11`; Phase31 protected returns remain unopened.
- **Active Phase31: SEC Form-4 Insider-Transaction Alpha.**
- Active branch: `phase-31-sec-insider-transaction-alpha`.
- Original feasibility `FEASIBILITY_FAIL` is permanently preserved. Root cause is preserved as a **Massive early-access/beta source-association/data-quality defect**; it was repaired only through generic fail-closed source-quality quarantine, never by weakening chronology.
- Frozen source-quality fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`.
- Frozen scientific policy fingerprint: `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`.
- Exactly four Phase31 hypotheses remain frozen: broad/clustered purchase LONG and broad/clustered sale SHORT.
- Historical entry = first post-filing XNYS session open; primary exit = t+20 XNYS close; primary performance = SPY-relative after-cost return with positive unhedged mean also required.
- **Full historical Form-4 acquisition PASSED** on the target machine: 62 monthly shards, 2,993,648 raw rows, 2,992,608 authoritative rows, 1,040 quarantined rows, 187 contaminated accessions, 233 chronology seed rows, 15 missing-`transaction_code` seed rows.
- Acquisition read 0 target outcomes, 0 protected candidate rows, and 0 protected returns; all four frozen probe windows reconciled exactly.
- **Predictor-only Form-4 event construction PASSED** on target head `dbde716b79ae882bcfec412e1a13e1bb3c274f6a`: 2,992,608 authoritative rows scanned, 103,773 qualified accessions, 5,870 resolved noncontradictory events, 5,400 development predictor rows, and 343 protected predictor rows.
- Frozen development predictor SHA: `a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f`.
- Frozen protected predictor SHA: `d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27`.
- Predictor construction read **0 target outcomes and 0 protected returns** and performed zero provider/broker/order/PAPER/LIVE/automation writes.
- Current internal target = **development-only Phase31 performance evaluation** under the frozen four-hypothesis contract. Development stock/SPY outcomes may now be read only through the dedicated exact-session, split-censored, previous-session-regime path; protected predictor rows/returns remain unread.
- Development selection remains chronological first 75%, then 20-session purge, then internal validation; global Holm is across all four hypotheses; no runner-up substitution is allowed.
- Phase32 remains blocked until supported alpha exists.
- LIVE remains disabled. Automatic broker failover remains disabled.

See `docs/current_status.md` for exact hashes, thresholds, and handoff instructions.

## Remaining roadmap

- **Phase31:** SEC Form-4 Insider-Transaction Alpha — active.
- **Phase32:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase33:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase34:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase35:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase36:** Production Web Application, Operations & Deployment.
- **Phase37:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase38:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
