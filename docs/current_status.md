# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core source V2 and corrected semantic source V2 are accepted PASS. Semantic V1 remains retained `NOT ACCEPTED`. Zero market outcomes have been read in Phase32; the active target is a local source/taxonomy census before hypothesis freeze.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_semantic_source_qualification.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **semantic V2 source/taxonomy census, then scientific-contract freeze**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory.

## Protected holdout

Master protected outcome window remains `2026-05-12..2026-08-11`.

Phases26–31 and all Phase32 source work have read zero protected returns. Semantic V1 diagnosis, semantic V2 qualification, and the source census read zero target/protected market outcomes. The holdout remains outcome-unopened.

## Phase32 core source V2 — ACCEPTED PASS

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine PASS retained: 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted authoritative SEC metadata source remains `data.sec.gov/submissions`; accepted discovery remains Massive `/stocks/filings/vX/index?form_type=8-K`.

Accepted timing remains:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

## Semantic V1 — RETAINED NOT ACCEPTED

Fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1's exact ticker-equality and exact `supporting_text`-inside-`items_text` invariants were diagnosed as invalid provider-scope assumptions. V1 remains immutable failed evidence and grants no authority.

## Semantic V2 — ACCEPTED PASS

Contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Research boundary:

`2021-08-16`

Target-machine PASS evidence:

- taxonomy: **119 rows**, version **1.0**;
- five probe windows all nonempty with complete original-8-K accession overlap;
- disclosure rows: **7,468**;
- sampled accessions: **30**;
- Massive Text records: **30**;
- official SEC records: **30**;
- ticker relations: 22 direct disclosure/index overlaps, 2 disclosure/text historical-map agreements with differing index ticker, 6 fully unmapped;
- target outcome rows: **0**;
- protected candidate rows: **0**;
- protected return rows: **0**;
- all provider/broker/order/PAPER/LIVE mutations: **0**.

Accepted filing identity is exact accession + zero-padded CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata only. `items_text` lexical comparison remains diagnostic only.

## Exact next target — pre-return source census

Run:

`scripts/run_phase32_semantic_v2_source_census.py`

The census uses only immutable accepted V2 artifacts already on disk. It makes zero network calls, hash-checks taxonomy/disclosure evidence, and reports category/accession/CIK coverage. It reads no market outcomes.

After the census passes, use only source/taxonomy semantics and non-performance feasibility to freeze the complete finite Phase32 scientific contract. **No development return may be opened before that contract and the point-in-time instrument-resolution rule are fingerprinted and frozen.**
