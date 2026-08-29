# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — core source V2 and corrected semantic source V2 are accepted PASS. Semantic V1 remains retained `NOT ACCEPTED`. Alpha hypotheses remain unfrozen, zero market outcomes are authorized, and Phase33 remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Accepted core source progression

V1 archive/header acquisition remains retained as failed source-history evidence. Six attempts failed without market-outcome reads. ATLAS diagnosed that path and formally versioned the replacement rather than weakening validation.

Core V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine result: **PASS** with 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

Accepted discovery remains Massive `/stocks/filings/vX/index?form_type=8-K`. Authoritative metadata remains official `data.sec.gov/submissions`, with timing:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

## Semantic source progression

Semantic V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1 remains `NOT ACCEPTED`. It failed exact ticker equality and exact normalized `supporting_text` substring-in-`items_text` checks. Diagnosis showed these were invalid source-scope invariants, not reasons to weaken provenance. Filing identity is accession+CIK+SEC reconciliation; ticker is mapping metadata; `items_text` is a narrower core-Items projection. V1 remains immutable evidence.

Corrected semantic V2 contract:

`phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes`

Fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic research boundary:

`2021-08-16`

Target-machine semantic V2 result: **PASS**.

Accepted evidence:

- taxonomy: 119 rows, version 1.0;
- all five retained windows contain semantic disclosure rows with complete exact original-8-K accession overlap;
- 7,468 disclosure rows total;
- 30 sampled accessions, 30 Massive Text records, and 30 official SEC records;
- ticker relations: 22 direct disclosure/index overlaps, 2 disclosure/text historical-map agreements with differing index ticker, and 6 fully unmapped;
- zero target outcomes, zero protected candidates, zero protected returns, and zero provider/broker/order/PAPER/LIVE authority.

Full source contract and retained V1 diagnosis are in `docs/phase32_semantic_source_qualification.md`.

## Exact current action — source/taxonomy census

Before freezing hypotheses, run:

`scripts/run_phase32_semantic_v2_source_census.py`

This is a deterministic local-only census over the immutable accepted V2 evidence. It:

- makes zero network calls;
- verifies accepted V2 report/fingerprint and zero-outcome state;
- hash-checks the retained taxonomy and disclosure files;
- aggregates disclosure rows, unique accessions, unique CIKs, windows present, and mapped/unmapped ticker rows by primary, secondary, and tertiary taxonomy category;
- outputs the full 119-row taxonomy with non-performance probe-window counts;
- reads no stock/SPY/options outcomes.

The census is source feasibility evidence only. Category counts cannot establish alpha and cannot be used as performance evidence.

## What must be frozen before any return read

After the census passes, ATLAS must freeze one complete scientific contract containing:

1. a finite economically motivated event hypothesis family and predeclared LONG/SHORT direction for each candidate;
2. event aggregation, duplicate, contradiction, multi-disclosure, and amendment treatment;
3. exact point-in-time issuer/instrument resolution from filing CIK/accession to the tradable security valid at the decision time;
4. decision session using the accepted SEC acceptance-time rule;
5. fixed outcome horizon(s) and exit convention;
6. benchmark/hedging convention and requirement for economically positive unhedged performance where applicable;
7. realistic transaction/slippage costs;
8. mandatory minimum rows, sessions, unique issuers/tickers, and concentration limits;
9. dependence-aware inference for clustered/overlapping outcomes;
10. multiplicity/selection-bias correction across the entire frozen family;
11. robustness requirements;
12. development/internal/protected chronology and purge rules;
13. winner, finalist, no-runner-up, and finalist-only protected-read rules.

No development return may be inspected before this contract is fingerprinted and frozen.

## Authority boundary

Allowed now: immutable semantic V2 evidence, local source/taxonomy census, validators/tests, scientific-contract construction from source semantics, and documentation.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

Phase33 signal-to-trade remains blocked.
