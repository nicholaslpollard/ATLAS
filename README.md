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

Retained Phase32 source-incident history is in `docs/phase32_sec_edgar_access_incident.md`, `docs/phase32_massive_text_multiplicity_incident.md`, `docs/phase32_crash_cache_corruption_incident.md`, and `docs/phase32_sec_submissions_shard_boundary_incident.md`.

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

Long-running target-machine runners must provide lightweight terminal progress instead of appearing idle. Prefer a simple `x / total completed` indicator, optionally with percent complete; when a meaningful total is unavailable, report the current date/window/batch plus a completed count. Update at useful intervals without noisy per-record logging. Progress reporting is operational observability only and must never alter scientific logic, source evidence, chronology, acceptance criteria, or authority boundaries.

## Current state — 2026-08-29

- Accepted foundation: **through Phase31**.
- Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; supported modern alpha remains **0**.
- Phase31 PR #35 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Master protected outcome window remains `2026-05-12..2026-08-11` and remains outcome-unopened.
- **Active Phase32: SEC 8-K Material Corporate-Event Alpha.**
- Active branch: `phase-32-sec-8k-material-event-alpha`.

### Retained Phase31 feasibility provenance — historical only

This block preserves the accepted Phase31-era handoff required by the retained validators; it does not change the current active Phase32 state.

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

The first multi-filer target-machine stop was accession `0000034903-25-000028`: multiple original-8-K index rows legitimately shared one accession. The corrected acquisition requires an issuer-CIK-matching index row, retains other index CIKs as co-filer provenance, and prevents co-filer tickers from entering issuer PIT mapping.

A later target-machine stop at accession `0001057877-22-000019` exposed the same multiplicity on semantic disclosures. The acquisition had still grouped candidate disclosure rows by accession alone. The corrected filing-entity source key is now `EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE`: disclosure rows are partitioned by issuer CIK, each filing entity is independently reconciled to SEC/Text/index evidence, and only that entity's ticker mappings may feed PIT identity. A conflicting filing date under one accession remains a hard failure. Evidence is written as `candidate_filing_entity_records.jsonl`, and report/runner counts distinguish unique accessions from filing entities.

A third source-only stop at accession `0001140361-26-029471` / CIK `0002017526` showed that one filing entity can legitimately have multiple Massive Text rows when a ticker transition is represented. The read-only local diagnostic proved the two rows were identical in every non-ticker field and differed only by ticker (`FRNM` versus `PCSC`). The corrected rule accepts one or more Text rows only when every non-ticker field is identical, preserves all ticker variants for exact PIT identity checks, hashes the complete Text-row set plus the shared non-ticker record, and still fails closed on any non-ticker conflict. See `docs/phase32_massive_text_multiplicity_incident.md`.

The target machine later suffered an abrupt operating-system crash while unrelated software was being installed. A complete local cache parse identified exactly two all-null reconstructible JSON caches among more than 93,000 JSON/JSONL cache files. Exact byte hashes were preserved, both files were quarantined under a fail-closed repair contract, the full cache parse then passed, and acquisition resumed without changing any scientific or source rule. See `docs/phase32_crash_cache_corruption_incident.md`.

The resumed acquisition then stopped at `27,225 / 36,309` on News Corp accession `0001564708-23-000471` / filing date `2023-10-05`. Read-only official SEC diagnostics proved the root `filings.files` metadata declared its historical shard only through `2023-10-04`, while that exact SEC-declared shard actually contains the target `2023-10-05` original 8-K and its acceptance timestamp. The corrected SEC lookup therefore preserves exact date-covering shards as primary and permits a **one-calendar-day adjacent SEC-declared shard only when no date-covering shard exists**. URLs are never guessed, the two-shard hard bound remains, and exact accession + exact requested filing date + original `8-K` remain mandatory. See `docs/phase32_sec_submissions_shard_boundary_incident.md`.

All source corrections occurred before any development or protected return read. The frozen scientific fingerprint, hypotheses, chronology, costs, sample gates, multiplicity controls, identity-v4 rules, and protected-evidence boundary are unchanged. Existing source caches remain reusable.

Only after this source/predictor gate passes and an independent local source/lineage validation freezes its evidence hashes may development returns be opened under the unchanged contract.

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
