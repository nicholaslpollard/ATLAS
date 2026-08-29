# Phase 32 — Semantic 8-K Source Qualification

**Status:** ACTIVE — semantic V1 is retained `NOT ACCEPTED`; corrected semantic V2 is frozen and awaits target-machine execution. No alpha hypothesis is frozen and no market outcome is authorized.

## Accepted core source foundation

Phase32 core V2 remains accepted PASS under fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

It established Massive original-8-K discovery plus official `data.sec.gov/submissions` reconciliation, with exact accession/form/filing date/acceptance metadata and zero market outcomes.

## Semantic V1 — retained rejected evidence

V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine V1 returned `NOT ACCEPTED` on:

- `all_sampled_tickers_align`;
- `all_sampled_supporting_text_is_grounded`.

The failure was diagnosed before any workaround or return read.

### Root cause 1 — wrong ticker invariant

V1 treated exact cross-endpoint ticker equality as filing identity. That is not a valid invariant:

- disclosure ticker arrays may be empty when the provider has no mapped ticker;
- EDGAR index/text/disclosure ticker metadata can reflect different mapping states;
- historical symbol changes can make two correct records for the same accession+CIK carry different symbols.

The retained diagnostic showed four fully unmapped samples and one historical mapping difference where disclosure/text agreed on `SLGG` while the index carried `SLE`, yet exact CIK and SEC filing identity reconciled.

Corrected rule: **filing identity is exact accession + zero-padded issuer CIK + filing date + official SEC reconciliation. Ticker fields are mapping metadata only.** Empty or historically different ticker mappings are recorded, never silently normalized, and cannot by themselves establish or break filing identity. Any later market-outcome linkage must use a separately frozen point-in-time instrument-resolution rule.

### Root cause 2 — wrong text-scope invariant

V1 required every normalized `supporting_text` value to be an exact substring of Massive `items_text`.

That compared different source scopes. Massive describes:

- `supporting_text` as the filing excerpt used for the semantic classification;
- 8-K `items_text` as parsed text from the core Items sections.

The retained diagnostic confirmed the mismatch was usually source-scope/formatting rather than unrelated text: ten of eleven nonexact supporting rows preserved every normalized token in filing order within `items_text`; one row had 0.228 ordered coverage, consistent with the fact that the full filing can contain material outside the core Items projection. Exact substring equality against `items_text` is therefore not a valid full-filing grounding test.

Corrected rule: **supporting text must be nonblank and attached to the exact accession/CIK/date whose categories exist in the versioned taxonomy.** `items_text` remains mandatory for the sampled filing, but lexical comparison is retained as a diagnostic only and grants no pass/fail authority.

### Root cause 3 — unsupported history cutoff

V1 encoded a January-2022 semantic start. The retained source evidence itself contradicts using that as the Phase32 research boundary: the `2021-08-16..2021-08-20` probe contained **1,475** disclosure rows, all **1,475** overlapping exact original-8-K accessions.

V2 therefore does not inherit a marketing-date cutoff. It requires empirical semantic coverage beginning at the existing Phase32 research boundary:

`2021-08-16`

This authorizes no claim about coverage before that date.

## Frozen semantic V2 contract

Contract version:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Frozen fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Frozen probe windows:

1. research boundary: `2021-08-16..2021-08-20`;
2. early history: `2022-01-03..2022-01-07`;
3. mid history: `2023-08-14..2023-08-18`;
4. development boundary: `2026-05-04..2026-05-08`;
5. protected boundary: `2026-08-07..2026-08-11`.

Every window is covered. Each deterministically samples at most six unique disclosure-bearing original-8-K accessions.

## V2 acceptance checks

Without reading stock/SPY/options outcomes, V2 must prove:

- taxonomy is nonempty and versioned;
- every probe window contains semantic disclosure rows;
- every disclosure row in each probe window overlaps an exact original-8-K accession from the Massive EDGAR index;
- every probe window produces deterministic samples;
- sampled disclosure/index/text records reconcile exact accession, zero-padded issuer CIK, and filing date;
- every sampled accession has exactly one matching original-8-K Massive Text record for the queried CIK/date;
- every sampled semantic category exists in the fetched taxonomy;
- every sampled `supporting_text` is nonblank;
- official SEC submissions metadata independently reconciles accession, original `8-K`, filing date, issuer CIK, and nonempty acceptance timestamp;
- ticker relations are recorded but ticker is never used as filing identity;
- `items_text` lexical diagnostics are preserved but explicitly have no acceptance authority;
- V2 evidence is written to a new immutable `v2` evidence namespace; V1 is not rewritten;
- target outcomes, protected candidates, protected returns, provider writes, broker reads/writes, orders, PAPER, LIVE, automation writes, and automatic broker failover remain zero/disabled.

## Authority boundary

A V2 PASS would establish only that the semantic source is suitable for defining the finite Phase32 predictor family. It would **not** establish alpha, open the holdout, satisfy Phase33, or authorize trading.

After a V2 PASS, ATLAS may use source/taxonomy evidence only to freeze the complete Phase32 scientific contract before any development return read. Point-in-time instrument/ticker resolution must be explicitly frozen in that contract because ticker metadata is not filing identity.

## Failure rule

Any V2 failure stops progression. Diagnose and repair the actual source/provenance defect first. Do not weaken accession, CIK, SEC, chronology, taxonomy, immutability, or authority checks to force PASS.

## Exact target

Validator:

`scripts/validate_phase32_semantic_v2.py`

Runner:

`scripts/run_phase32_semantic_feasibility_v2.py`

Expected fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`
