# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md`;
2. `docs/current_status.md`;
3. `docs/alpha_gate_sec_xbrl_fundamental_quality.md`;
4. `docs/alpha_gate_sec_xbrl_pit_audit.md`;
5. `docs/phase32_closeout.md`;
6. `docs/phase32_sec_8k_material_event_alpha.md`;
7. `docs/phase32_scientific_contract.md`;
8. `docs/phase32_predictor_independent_acceptance.md`;
9. `docs/phase32_development_evaluation.md`;
10. `docs/phase32_finalist_blindness_audit.md`;
11. `docs/phase_flow.md` and `docs/phase_plain_english_contract.md`;
12. accepted code, validators, CI/PR evidence.

Retained Phase32 source-incident history remains in `docs/phase32_sec_edgar_access_incident.md`, `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, and `docs/phase32_sec_submissions_shard_boundary_incident.md`.

## Locked architecture

`market/reference/regulatory -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic alpha evaluation -> candidate promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> SHADOW/PAPER/LIVE execution -> learning -> browser control plane -> production operations`

- Massive = primary market/reference/regulatory provider where entitlement and PIT semantics are proven.
- Current Massive plan = **Stocks Starter**; unrelated paid datasets/plans are never assumed.
- Official SEC EDGAR/XBRL = read-only authoritative regulatory provenance when explicitly phase-gated.
- Parquet = durable analytical lake; DuckDB = analytical engine; PostgreSQL = later operational state.
- Webull = primary PAPER/sandbox and intended primary LIVE broker only after separate LIVE acceptance.
- Alpaca = manual secondary broker; **no automatic broker failover**.
- ML/AI = evidence/audit layers, never unilateral trading authority.
- Browser GUI = operator surface, never a second trading engine.

## Operating rule

One numbered phase is one acceptance gate:

`PLAIN-ENGLISH PHASE START -> DEFINE/LOCK -> IMPLEMENT -> FOCUSED TESTS -> FULL PHASE-END ACCEPTANCE -> PLAIN-ENGLISH PHASE END -> DOCUMENT -> ACCEPT OR REPAIR -> MERGE -> NEXT PHASE`

Use the largest safe coherent work package. Do not create conversational micro-gates for implementation steps that do not change scientific/provider/broker/destructive/LIVE authority. Target-machine checks remain mandatory when repository CI cannot prove local data/provider/artifact facts.

If an error occurs, ATLAS identifies the root cause, implements and tests the proper correction, and only then continues. Validators or scientific rules are never weakened to obtain PASS. Failed approaches remain evidence. Zero candidates/trades is legitimate.

Material decisions and completed gates must be synchronized into roadmap/status/phase docs/README before work is complete.

## Current state — 2026-08-29 (America/New_York)

- Accepted foundation: **through Phase32**, merged into `main`.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well.
- Historical supported modern alpha remains **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR #37 / merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- Phase32 is `ACCEPTED_NEGATIVE`; protected return rows read = 0 and the holdout remains unconsumed.
- Master protected outcome window `2026-05-12..2026-08-11` remains **protected-return unopened**.
- Phase32 development finalist `solvency_distress_short` did not earn `SUPPORTED` authority.
- Phase33 signal-to-trade remains blocked.
- SEC XBRL source feasibility is accepted **`FEASIBILITY_PASS`** on exact head `5a8c15f95417390d0d64ff240977adfb38a20c45`.
- Accepted XBRL feasibility census: **200** successful Company Facts documents, **170** accrual-history-ready issuers, **92** profitability-history-ready issuers, zero target/protected reads.
- Current research branch: `alpha-gate-sec-xbrl-fundamental-quality-pit-audit`.
- Current research authority: frozen source-only XBRL PIT chronology/restatement/identity audit; **no alpha hypotheses frozen and zero market outcomes authorized**.
- LIVE and automatic broker failover remain disabled.

### Phase32 closeout

Phase32 policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Phase32's frozen scientific family remained exactly five hypotheses throughout development, finalist selection, and closeout.

The independent finalist blindness / lineage audit reproduced `solvency_distress_short` and froze a protected source-only population of **46 event rows / 33 signal sessions / 40 unique instruments** against frozen minimums of **50 / 20 / 20**.

Finalist audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Protected plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Protected plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

The 46-row population fails the mandatory 50-row gate before protected performance is opened. Phase32 therefore closed `ACCEPTED_NEGATIVE` with protected return rows read = 0 and protected holdout consumed = false. No threshold relaxation, alternate finalist, or post-result 8-K retune is authorized.

### Current pre-Phase33 alpha gate — SEC XBRL fundamental quality / accrual PIT audit

ATLAS has opened a **materially different information mechanism**: point-in-time standardized quarterly fundamentals from original SEC 10-Q/10-K XBRL facts, aimed at eventual profitability, cash-vs-accrual quality, and fundamental-change hypotheses.

The source-only feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

The target-machine source census returned **`FEASIBILITY_PASS`** with 4,400 source-inventory CIKs, 200/200 successful Company Facts documents, 170 accrual-history-ready issuers, 92 profitability-history-ready issuers, and zero market/protected outcome reads.

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

Current frozen PIT source-audit contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Current PIT audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

The audit uses exactly 40 deterministic feasibility-ready issuers and up to 5 evenly spaced original 10-Q/10-K accessions per issuer. It binds each fact to exact accession, reconciles official SEC `acceptanceDateTime`, preserves later comparative/restated values as separate later accession versions, and maps issuer CIK to Massive stock identity at the first XNYS session strictly after acceptance.

Frozen source gates require >=36 Company Facts successes, >=180 selected original filings, >=170 exact SEC metadata reconciliations, >=170 acceptance-time decision sessions, >=120 unambiguous PIT instrument mappings, >=30 issuers with at least 3 unambiguous mappings, and zero same-accession semantic-context conflicts.

This gate reads **zero stock/SPY/options/market outcomes and zero protected returns**. An `AUDIT_PASS` can authorize only the next finite scientific-policy freeze before any performance read. It cannot create a supported strategy or unblock Phase33.

See `docs/alpha_gate_sec_xbrl_fundamental_quality.md` and `docs/alpha_gate_sec_xbrl_pit_audit.md`.

## Remaining roadmap

- **Current pre-Phase33 alpha gate:** SEC XBRL fundamental-quality/accrual source-only PIT chronology/restatement/identity audit.
- **Phase33:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked on supported alpha.
- **Phase34:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase35:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase36:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase37:** Production Web Application, Operations & Deployment.
- **Phase38:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase39:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent boundaries

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; never fabricate history; finalized facts outrank provisional state; fail closed on stale/missing/uncertain data or broker state; enforce valid geometry and portfolio risk; treat research ideas as hypotheses rather than evidence; never weaken a gate after results; protected performance is finalist-only; no automatic broker failover; PAPER does not imply LIVE; and LIVE exists only after the final separately accepted authority gate.
