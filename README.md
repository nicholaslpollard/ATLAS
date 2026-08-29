# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is the greenfield successor/redesign path for Chart Monitor. Its objective is to use trustworthy market/regulatory evidence, validated quantitative edge, disciplined risk management, appropriate stock/options construction, reliable execution, and outcome learning to make educated trades with the goal of growing account equity after realistic costs. Profit is never guaranteed and trade frequency is not a success criterion.

The legacy Chart Monitor remains preserved while ATLAS matures through SHADOW/PAPER and, only after a separately accepted final authority gate, controlled LIVE operation.

## Continuation order

Every new ATLAS work session should read:

1. `docs/roadmap.md` — normative mission, architecture, acceptance model, and remaining roadmap;
2. `docs/current_status.md` — exact current handoff;
3. `docs/phase32_sec_8k_material_event_alpha.md` — active phase;
4. `docs/phase32_semantic_source_qualification.md` — exact active internal gate;
5. `docs/phase31_closeout.md` — latest accepted numbered-phase closeout;
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
- Phase31 independent closeout: `PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF`; zero survivors/winners/finalists/support; zero protected reads.
- Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.

### Phase32 core source feasibility

Accepted V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS** with **6,048** Massive original-8-K index rows, **5,272** ticker-linked rows, **48** official SEC records, **94** item codes, **0** SEC filing-date mismatches, and **0** target/protected return reads.

Accepted core source = Massive `/stocks/filings/vX/index?form_type=8-K` plus official SEC `data.sec.gov/submissions` metadata. Conservative timing boundary remains:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

### Exact active target

Before freezing alpha hypotheses, ATLAS is qualifying Massive's semantic 8-K sources:

- `/stocks/filings/8-K/vX/disclosures`
- `/stocks/filings/8-K/vX/text`
- `/stocks/taxonomies/vX/disclosures`

Frozen semantic-source contract:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Conservative semantic history start: `2022-01-03`, subject to the source-only qualification gate. The runner verifies source history, taxonomy membership/versioning, original-8-K overlap, provider-native ticker alignment, supporting-text grounding, exact SEC provenance, immutable evidence, and zero market outcomes.

Runner:

`scripts/run_phase32_semantic_feasibility.py`

If it fails, stop and repair the source/provenance defect. If it passes, the next step is to freeze the complete finite Phase32 scientific hypothesis contract before any development return is read.

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
