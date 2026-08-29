# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — core source feasibility V2 is accepted; semantic V1 is retained `NOT ACCEPTED`; corrected semantic V2 is frozen and awaiting target-machine execution. Alpha hypotheses remain unfrozen, zero market outcomes are authorized, and Phase33 remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Accepted core source progression

V1 archive/header acquisition remains retained as failed source-history evidence. Six attempts failed without market-outcome reads. ATLAS diagnosed that path and formally versioned the source contract before moving to official structured SEC submissions metadata.

Core V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS** with 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted discovery remains Massive `/stocks/filings/vX/index?form_type=8-K`. Authoritative metadata remains official `data.sec.gov/submissions`, with timing:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

## Semantic V1 — retained NOT ACCEPTED

V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1 failed exact ticker equality and exact normalized `supporting_text` substring-in-`items_text` checks. The target-machine diagnostics established the root cause without any return read:

- accession+CIK+official SEC metadata reconcile even when ticker mappings are empty or historically different;
- provider ticker fields are mapping metadata, not stable filing identity;
- disclosure `supporting_text` refers to the filing, while Massive 8-K `items_text` is the narrower core-Items projection;
- the August 2021 research-boundary probe already contains 1,475 semantic disclosure rows with 1,475 exact original-8-K accession overlaps, invalidating V1's inherited January-2022 cutoff for this study.

V1 remains preserved and is not weakened or rewritten.

## Corrected semantic V2 — frozen

Contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic research boundary:

`2021-08-16`

Sources:

- `/stocks/filings/8-K/vX/disclosures`
- `/stocks/filings/8-K/vX/text`
- `/stocks/taxonomies/vX/disclosures`
- `/stocks/filings/vX/index?form_type=8-K`
- official `data.sec.gov/submissions`

V2 validates source/provenance only. Filing identity is exact accession + zero-padded issuer CIK + filing date + independent SEC reconciliation. Ticker mappings are preserved verbatim and classified but have no filing-identity authority. `supporting_text` must be nonblank and taxonomy-linked to the exact filing; `items_text` remains required but lexical comparison is diagnostic because it represents a narrower source scope.

V2 requires empirical coverage at all five retained windows beginning `2021-08-16`, samples at most six exact original-8-K accessions per window, writes new immutable `/v2` evidence, and reads zero market outcomes.

Full source contract: `docs/phase32_semantic_source_qualification.md`.

Exact target:

`scripts/validate_phase32_semantic_v2.py`

`scripts/run_phase32_semantic_feasibility_v2.py`

## What remains unfrozen

No Phase32 alpha candidate exists. No event direction, horizon, threshold, ranking, or return-based selection is authorized.

Only after semantic V2 passes may ATLAS use source/taxonomy evidence to freeze the finite hypothesis family, event aggregation/contradiction/amendment rules, point-in-time instrument identity, decision session, horizons, benchmark, costs, sample/concentration gates, dependence-aware inference, multiplicity, robustness, development/internal/protected chronology and purge, winner/finalist rules, and finalist-only protected read.

Ticker-to-market-data resolution is explicitly **not** solved by the semantic source gate; it must be frozen as a point-in-time identity rule before outcomes are linked.

## Authority boundary

Allowed now: bounded read-only semantic V2 source calls, official SEC submissions reads, immutable local source/report writes, validators, and tests.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

Phase33 signal-to-trade remains blocked.
