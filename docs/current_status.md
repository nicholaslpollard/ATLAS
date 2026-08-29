# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-29. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core V2, semantic V2, and the source/taxonomy census are accepted PASS. The complete Phase32 scientific contract is frozen before any market-outcome read. Full-history predictor/source acquisition is active and remains outcome-blind.**

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

## Retained Phase31 feasibility handoff provenance — historical only

This block preserves exact accepted-era Phase31 handoff evidence required by the retained Phase31 validators. It does not supersede the active Phase32 state above.

- Declared Massive plan: **Stocks Starter**.
- Historical active branch: `phase-31-sec-insider-transaction-alpha`.
- Original feasibility disposition: `FEASIBILITY_FAIL`.
- Diagnostic head: `80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`.
- Violation artifact SHA-256: `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`.
- Source-quality repair fingerprint: `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`.
- Source-quality policy: `RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`.
- Root-cause classification: **Massive beta source-association/data-quality defect**.
- Exact historical next handoff runner: `scripts/run_phase31_form4_source_quality_repair.py`.
- Frozen Phase31 scientific policy fingerprint: `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`.
- Accepted source-quality target retained **45,915** authoritative rows.
- Historical post-freeze acquisition runner: `scripts/run_phase31_form4_acquisition.py`.

The original failed evidence remains preserved; the later repair and final Phase31 `ACCEPTED_NEGATIVE` closeout do not rewrite that incident.

## Protected holdout

Master protected outcome window remains `2026-05-12..2026-08-11`.

**Phase32 market outcomes remain unread.** Phases26–31 and all Phase32 source qualification/census/contract-freeze/acquisition work to date have read zero protected returns. The holdout remains outcome-unopened.

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

### Joint/multi-filer accession reconciliation — corrected before outcomes

The full-history acquisition target-machine run stopped, before any market-outcome read, at accession `0000034903-25-000028` because the initial acquisition implementation incorrectly required **every** Massive index row sharing an accession to have the disclosure issuer CIK. Official SEC evidence shows this accession is a legitimate joint 8-K filed by Federal Realty Investment Trust (`CIK 0000034903`) and Federal Realty OP LP (`CIK 0001901876`).

The corrected acquisition invariant is:

- all index rows sharing the accession must retain the same filing date and original form `8-K`;
- at least one index row must match the semantic disclosure issuer CIK exactly;
- nonmatching CIK rows are preserved as legitimate co-filer provenance, not treated as corrupt rows;
- only issuer-CIK-matching index rows may contribute index ticker mappings to PIT instrument resolution;
- if the disclosure issuer CIK is absent from the accession's index rows, acquisition still fails closed.

This correction changes no frozen hypothesis, direction, timing, outcome, cost, sample gate, multiplicity rule, identity-v4 rule, or protected-evidence boundary. Development and protected returns remain unopened.

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

Complete and independently accept **full-history Phase32 source/predictor acquisition** for `2021-08-16..2026-08-11` under fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`, including the corrected joint/multi-filer accession reconciliation above.

It must acquire/reconcile original 8-K discovery, semantic disclosure evidence, official SEC acceptance metadata, and point-in-time instrument mapping while reading **zero stock/SPY/options outcomes**. Only after that predictor/source gate passes may development returns be opened under the frozen contract.
