# Phase 32 — Semantic 8-K Source Qualification

**Status:** ACCEPTED PASS. Semantic V1 remains retained `NOT ACCEPTED`; corrected semantic V2 passed on the target machine. No alpha hypothesis is frozen and no market outcome has been read.

## Accepted core source foundation

Phase32 core V2 remains accepted PASS under fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

It established Massive original-8-K discovery plus official `data.sec.gov/submissions` reconciliation, with exact accession/form/filing date/acceptance metadata and zero market outcomes.

## Semantic V1 — retained rejected evidence

V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine V1 returned `NOT ACCEPTED` on exact ticker equality and exact normalized `supporting_text` substring-in-`items_text` checks. Root-cause diagnosis established that those were invalid source-scope invariants:

- filing identity is exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation;
- ticker fields are mapping metadata and may be empty or historically different;
- disclosure `supporting_text` is tied to the filing, while 8-K `items_text` is the narrower core-Items projection;
- retained August 2021 evidence contained 1,475 disclosure rows with 1,475 exact original-8-K accession overlaps, so V1's January-2022 cutoff was rejected for this study.

The Massive endpoint documentation supplied during V1 states: Plan History is **not applicable** to the endpoint. That statement is retained as source provenance and is not converted into a fabricated historical cutoff; V2 relies on empirical coverage beginning at the existing Phase32 research boundary.

V1 remains immutable failed evidence and is not rewritten by V2.

## Accepted semantic V2 contract

Contract version:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Accepted fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic research boundary:

`2021-08-16`

Frozen identity rule:

`EXACT_ACCESSION_PLUS_ZERO_PADDED_CIK_PLUS_SEC_RECONCILIATION`

Frozen ticker rule:

`MAPPING_METADATA_ONLY_NOT_IDENTITY_EMPTY_OR_HISTORICAL_DIFFERENCE_ALLOWED_AND_RECORDED`

Frozen supporting-text rule:

`NONBLANK_SUPPORTING_TEXT_LINKED_TO_EXACT_ACCESSION_CIK_DATE_AND_TAXONOMY;ITEMS_TEXT_SCOPE_CHECK_DIAGNOSTIC_ONLY`

## Target-machine PASS evidence

Semantic V2 passed with:

- taxonomy rows: **119**;
- taxonomy versions: **1.0** only;
- taxonomy SHA-256: `b1bcb0037d2d17a36f1b72b8e260b32a611a81b36b831af5c5a6423e660d28a6`;
- research boundary `2021-08-16..2021-08-20`: **1,218** index rows, **1,475** disclosures, **1,475** exact overlaps, 6 samples;
- early history `2022-01-03..2022-01-07`: **1,177 / 1,571 / 1,571**, 6 samples;
- mid history `2023-08-14..2023-08-18`: **1,305 / 1,351 / 1,351**, 6 samples;
- development boundary `2026-05-04..2026-05-08`: **2,579 / 2,122 / 2,122**, 6 samples;
- protected boundary `2026-08-07..2026-08-11`: **946 / 949 / 949**, 6 samples;
- total disclosure rows: **7,468**;
- sampled accessions: **30**;
- Massive Text records fetched: **30**;
- official SEC records fetched/reconciled: **30**;
- ticker relations: **22** `DISCLOSURE_INDEX_OVERLAP`, **2** `DISCLOSURE_TEXT_AGREE_INDEX_DIFFERS`, **6** `ALL_UNMAPPED`;
- `items_text` diagnostics: **48** disclosure rows checked, **36** exact normalized substrings, minimum ordered-token coverage **0.22784810126582278**, mean **0.9839135021097046**; this remains diagnostic only;
- target outcome rows read: **0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE: **0 / 0 / 0 / 0 / 0 / 0**.

This PASS establishes that the semantic source is suitable for defining a finite Phase32 predictor family. It does **not** establish alpha, consume the holdout, satisfy Phase33, or authorize trading.

## Exact next target — source/taxonomy census

Before any hypothesis is frozen, ATLAS performs one deterministic census over the immutable accepted V2 evidence:

`scripts/run_phase32_semantic_v2_source_census.py`

The census:

- performs **zero network calls**;
- hash-checks the accepted V2 taxonomy/disclosure artifacts against the accepted report;
- reads **zero stock/SPY/options outcomes**;
- reports taxonomy structure plus disclosure/accession/CIK coverage by primary, secondary, and tertiary category;
- records mapped versus unmapped ticker rows without treating ticker as issuer identity;
- exists only to support a finite, economically coherent hypothesis freeze and mandatory feasibility/sample rules.

After the census passes, ATLAS must freeze the complete scientific contract before any development return read: finite hypotheses and directions, event aggregation/contradiction/amendment rules, point-in-time instrument resolution, decision session, horizons, benchmark, costs, sample/concentration gates, dependence-aware inference, multiplicity, robustness, chronology/purge, winner/finalist/no-runner-up rules, and finalist-only protected evidence.

## Authority boundary

Allowed now: immutable local semantic V2 source evidence, source/taxonomy census, validators, tests, and documentation.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

## Failure rule

Any census or subsequent contract-freeze defect stops progression. Diagnose and repair the actual cause first. Do not weaken source identity, chronology, taxonomy, immutability, sample rules, multiplicity, protected evidence, or authority to obtain PASS.
