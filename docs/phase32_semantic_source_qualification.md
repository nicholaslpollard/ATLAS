# Phase 32 — Semantic 8-K Source Qualification

**Status:** ACCEPTED PASS. Semantic V1 remains retained `NOT ACCEPTED`; corrected semantic V2 and the source/taxonomy census passed on the target machine. The Phase32 scientific policy is now frozen under fingerprint `0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88`; market outcomes remain unread.

## Accepted core source foundation

Core V2 fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

It established Massive original-8-K discovery plus official `data.sec.gov/submissions` reconciliation with exact accession/form/filing date/acceptance metadata and zero market outcomes.

## Semantic V1 — retained rejected evidence

V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Retained failed checks:

- `all_sampled_tickers_align`;
- `all_sampled_supporting_text_is_grounded`.

Root-cause diagnosis established that exact cross-endpoint ticker equality and exact normalized `supporting_text` substring-in-`items_text` were invalid source-scope invariants. Filing identity is accession + zero-padded CIK + SEC reconciliation; ticker is mapping metadata; disclosure `supporting_text` and core-Items `items_text` have different scopes.

The supplied Massive endpoint documentation states: Plan History is **not applicable** to the endpoint. V1's January-2022 cutoff was rejected after retained August-2021 semantic evidence showed 1,475 exact original-8-K disclosure overlaps. V1 remains immutable failed evidence and is not rewritten by V2.

## Semantic V2 — ACCEPTED PASS

Contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic research boundary: `2021-08-16`.

Frozen source rules:

- filing identity: `EXACT_ACCESSION_PLUS_ZERO_PADDED_CIK_PLUS_SEC_RECONCILIATION`;
- ticker: `MAPPING_METADATA_ONLY_NOT_IDENTITY_EMPTY_OR_HISTORICAL_DIFFERENCE_ALLOWED_AND_RECORDED`;
- supporting text: `NONBLANK_SUPPORTING_TEXT_LINKED_TO_EXACT_ACCESSION_CIK_DATE_AND_TAXONOMY;ITEMS_TEXT_SCOPE_CHECK_DIAGNOSTIC_ONLY`.

Accepted validator: `scripts/validate_phase32_semantic_v2.py`.
Accepted runner: `scripts/run_phase32_semantic_feasibility_v2.py`.

Target-machine V2 PASS evidence included taxonomy version 1.0 / 119 rows, **7,468** disclosure rows across five probe windows, complete original-8-K accession overlap in every window, 30 Massive Text records, 30 official SEC reconciliations, and zero target/protected outcome reads.

## Source/taxonomy census — ACCEPTED PASS

Contract:

`phase32-semantic-v2-source-census-v1-no-market-outcomes`

Accepted local runner:

`scripts/run_phase32_semantic_v2_source_census.py`

Target-machine census PASS:

- taxonomy rows: **119**;
- observed taxonomy rows: **112**;
- disclosure rows: **7,468**;
- unique accessions: **4,427**;
- unique CIKs: **3,097**;
- mapped ticker rows: **6,231**;
- unmapped ticker rows: **1,237**;
- target/protected outcome rows read: **0 / 0**.

The census was local-only, hash-checked accepted V2 evidence, made **zero network calls**, and contained no performance measure. It was used only to establish source-semantic feasibility for a finite hypothesis family. **No development return** was read before, during, or because of the census.

The five frozen families had non-performance probe-census row support of 433 (`equity_issuance_short`), 106 (`share_repurchase_long`), 53 (`financial_integrity_adverse_short`), 126 (`listing_distress_short`), and 64 (`solvency_distress_short`). These counts are not alpha rankings.

## Scientific handoff

Exactly **five hypotheses** are now frozen in `docs/phase32_scientific_contract.md` and `packages/backtesting/phase32_policy.py` under fingerprint:

`0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88`

The freeze includes exact taxonomy triples/directions, event aggregation and contradiction rules, SEC acceptance-time decision timing, 5-session horizon, PIT CIK-bound unique instrument resolution, SPY-relative/unhedged outcomes, costs, mandatory sample/concentration gates, 5-session dependence handling, global Holm-5 multiplicity, robustness, chronology/purge, winner/finalist/no-runner-up rules, and protected blindness.

No stock/SPY/options return was read in selecting any of those rules.

## Exact next target — full-history source/predictor acquisition

The next allowed action is **full-history** Phase32 predictor acquisition for `2021-08-16..2026-08-11` under the frozen policy. It must preserve original 8-K discovery, semantic disclosure taxonomy, official SEC acceptance metadata, exact accession/CIK lineage, and point-in-time instrument resolution while reading zero market outcomes.

Only after that full-history predictor/source gate passes may development returns be opened under the unchanged policy fingerprint.

## Authority boundary

Allowed now: accepted source evidence, frozen scientific policy, validators/tests, full-history source/predictor acquisition, PIT instrument mapping, and documentation.

Forbidden: stock/SPY/options outcomes before the predictor/source gate, protected returns before frozen finalists, provider mutations, broker/account reads or writes, orders, PAPER submissions, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

## Failure rule

Any full-history acquisition, identity, chronology, or contract defect stops progression. Diagnose and repair the actual cause first. Do not weaken source identity, taxonomy, chronology, sample rules, multiplicity, protected evidence, or authority to obtain PASS.
