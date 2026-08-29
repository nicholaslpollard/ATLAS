# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28. Phase31 remains closed `ACCEPTED_NEGATIVE`. Phase32 core 8-K source feasibility V2 is accepted PASS. Semantic V1 is retained `NOT ACCEPTED`; its root cause is diagnosed and corrected semantic V2 is frozen for target-machine execution. Zero market outcomes are authorized.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_semantic_source_qualification.md`, `docs/phase32_sec_edgar_access_incident.md`, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase31**.
- Phase26–31: all `ACCEPTED_NEGATIVE`.
- Accepted historical alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Active branch: `phase-32-sec-8k-material-event-alpha`.
- Active gate: **Phase32 — SEC 8-K Material Corporate-Event Alpha**.
- Active internal step: **run corrected semantic source qualification V2**.
- Phase33 signal-to-trade remains blocked.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory.

## Protected holdout

Master protected outcome window remains `2026-05-12..2026-08-11`.

Phases26–31 and all Phase32 source work have read zero protected returns. Semantic V1 diagnosis and semantic V2 contract construction read zero target/protected market outcomes. The holdout remains outcome-unopened.

## Phase32 core source feasibility V2 — ACCEPTED PASS

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine PASS retained: 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted timing remains `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

## Semantic V1 — RETAINED NOT ACCEPTED

Fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1 failed exact ticker equality and exact `supporting_text`-inside-`items_text` checks. Diagnosis established these were invalid invariants for the provider's documented field scopes rather than grounds to weaken provenance:

- filing identity is accession+CIK+SEC metadata, not ticker equality;
- ticker fields are mapping metadata and can be empty or historical;
- disclosure `supporting_text` is tied to the filing, while 8-K `items_text` is the narrower core-Items projection;
- the retained 2021 probe already contains 1,475 disclosures with 1,475 exact original-8-K overlaps, so the V1 January-2022 cutoff is rejected.

V1 remains immutable failed evidence.

## Corrected semantic V2 — FROZEN, AWAITING TARGET RUN

Contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Research boundary:

`2021-08-16`

V2 requires empirical semantic coverage across five retained Phase32 windows and validates exact accession+zero-padded CIK+filing-date identity, versioned taxonomy membership, nonblank supporting text, exact original-8-K Text linkage, and independent SEC accession/form/date/CIK/acceptance reconciliation. Ticker relations and `items_text` lexical comparisons are retained as diagnostics, not filing-identity gates.

V2 writes to a new immutable `/v2` evidence namespace and does not rewrite V1.

## Exact next target

```text
scripts/validate_phase32.py
scripts/validate_phase32_semantic.py
scripts/validate_phase32_semantic_v2.py
scripts/run_phase32_semantic_feasibility_v2.py
```

Expected semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

If V2 fails, stop and diagnose the exact source/provenance defect. If V2 passes, use source/taxonomy evidence only to freeze the complete finite Phase32 scientific hypothesis contract before any development return read. Point-in-time instrument resolution must be explicitly frozen before outcomes can be linked.
