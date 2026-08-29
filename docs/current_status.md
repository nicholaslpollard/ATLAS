# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core V2, semantic V2, and the source/taxonomy census are accepted PASS. The complete Phase32 scientific contract is now frozen before any market-outcome read.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_scientific_contract.md`, `docs/phase32_semantic_source_qualification.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **full-history Phase32 source/predictor acquisition under the frozen scientific contract**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory.

## Protected holdout

Master protected outcome window remains `2026-05-12..2026-08-11`.

**Phase32 market outcomes remain unread.** Phases26–31 and all Phase32 source qualification/census/contract-freeze work have read zero protected returns. The holdout remains outcome-unopened.

## Phase32 accepted source gates

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Core V2 target-machine PASS retained: 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted authoritative SEC metadata source remains `data.sec.gov/submissions`; accepted discovery remains Massive `/stocks/filings/vX/index?form_type=8-K`. Accepted timing remains `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

Rejected semantic V1 fingerprint remains immutable:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 target-machine PASS: taxonomy version 1.0 / 119 rows, 7,468 disclosure rows across all five probe windows, complete original-8-K accession overlap, 30 Massive Text samples, 30 official SEC reconciliations, and zero target/protected outcome reads.

Accepted filing identity is exact accession + zero-padded CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata only; `items_text` lexical comparison is diagnostic only.

## Source/taxonomy census — ACCEPTED PASS

Contract:

`phase32-semantic-v2-source-census-v1-no-market-outcomes`

Target-machine census PASS:

- taxonomy rows: **119**;
- observed taxonomy rows: **112**;
- disclosure rows: **7,468**;
- unique accessions: **4,427**;
- unique CIKs: **3,097**;
- mapped/unmapped ticker rows: **6,231 / 1,237**;
- target/protected outcome rows read: **0 / 0**.

The census was source-feasibility evidence only and did not rank candidates by performance.

## Phase32 scientific contract — FROZEN

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The earlier proposed `0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88` fingerprint was superseded before acceptance and before any market-outcome read when a pre-performance audit found that the proposal's medium-identity prose omitted ATLAS's required exact ticker component.

Exactly **five hypotheses** are frozen:

1. `equity_issuance_short`;
2. `share_repurchase_long`;
3. `financial_integrity_adverse_short`;
4. `listing_distress_short`;
5. `solvency_distress_short`.

Frozen core methodology:

- public availability: first XNYS regular-session open timestamp strictly after official SEC `acceptanceDateTime`;
- entry: decision-session open;
- exit: close five XNYS sessions later;
- primary outcome: 10-bps after-cost SPY-relative directional return, with positive unhedged performance also required;
- mandatory 25-bps stress mean;
- exact PIT unique instrument resolution bound to `instrument-identity-v4-no-issuer-level-medium-collapse`;
- accepted identity quality is strong or medium only: strong = Composite FIGI / Share Class FIGI; medium = CIK + exact provider-native ticker + primary exchange + security type;
- ticker+snapshot fallback identity, current-universe backprojection, and alias backfill are forbidden;
- 5-session purge and block bootstrap, 2,000 replicates;
- selection/internal/protected sample gates = 500/150/50 event rows, 200/60/20 sessions, 200/60/20 unique instruments;
- global `HOLM_BONFERRONI_GLOBAL_5`;
- at most one winner/finalist per direction and no runner-up substitution;
- protected returns forbidden until finalists are frozen and an independent blindness/lineage audit passes.

Full details: `docs/phase32_scientific_contract.md` and `packages/backtesting/phase32_policy.py`.

## Exact next target

Build and validate **full-history Phase32 source/predictor acquisition** for `2021-08-16..2026-08-11` under fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.

It must acquire/reconcile original 8-K discovery, semantic disclosure evidence, official SEC acceptance metadata, and point-in-time instrument mapping while reading **zero stock/SPY/options outcomes**. Only after that predictor/source gate passes may development returns be opened under the frozen contract.
