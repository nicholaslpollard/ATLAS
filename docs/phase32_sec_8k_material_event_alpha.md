# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — V2 core source feasibility accepted; semantic V1 is NOT ACCEPTED and Phase32 is stopped for root-cause diagnosis. Alpha hypotheses remain unfrozen, zero market outcomes are authorized, and Phase33 remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Accepted core source progression

V1 archive/header acquisition remains retained as failed source-history evidence. Six attempts failed without market-outcome reads. ATLAS diagnosed that path and formally versioned the source contract before moving to official structured SEC submissions metadata.

V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine V2 result: **PASS**.

Retained V2 totals:

- Massive original 8-K index rows: **6,048**
- ticker-linked rows: **5,272**
- sampled SEC records: **48**
- sampled SEC item codes: **94**
- SEC filing-date mismatches versus Massive: **0**
- target/protected outcome reads: **0 / 0**

Accepted discovery remains Massive `/stocks/filings/vX/index?form_type=8-K`. Authoritative metadata remains official `data.sec.gov/submissions`, with the conservative timing rule:

`FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`

## Semantic source V1 — NOT ACCEPTED

Semantic sources under evaluation:

- `/stocks/filings/8-K/vX/disclosures`
- `/stocks/filings/8-K/vX/text`
- `/stocks/taxonomies/vX/disclosures`

V1 contract:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine V1 returned **NOT ACCEPTED** because:

- `all_sampled_tickers_align` failed;
- `all_sampled_supporting_text_is_grounded` failed.

V1 read zero target/protected market outcomes and grants no authority.

A second source-contract defect was identified after the run: V1 encoded a January-2022 provider-history expectation and `2022-01-03` safe-history start that were not established by the Massive endpoint documentation supplied during Phase32. The supplied docs state Plan History is **not applicable**. That boundary is rejected and may not be propagated into a corrected contract without empirical source evidence.

The failed V1 remains preserved as source-only evidence; it is not deleted or rewritten.

## Exact current action

Run:

`scripts/diagnose_phase32_semantic_failure.py`

This diagnostic uses only the immutable local V1 source artifacts. It performs no provider calls and no market-outcome reads. It exposes the exact sampled ticker discrepancies and supporting-text/items-text mismatches so ATLAS can determine whether the failure is an implementation error, documented field-semantic difference, provider inconsistency, or genuine source infeasibility.

No ticker/grounding rule may be weakened before that cause is established.

## What remains unfrozen

No Phase32 alpha candidate exists. No event direction, horizon, threshold, ranking, or return-based selection is authorized.

Only after semantic-source provenance is correctly resolved may ATLAS freeze a finite hypothesis family, aggregation/contradiction/amendment rules, exact PIT identity, decision session, horizons, benchmark, costs, sample/concentration gates, dependence-aware inference, multiplicity, robustness, development/internal/protected chronology and purge, winner/finalist rules, and finalist-only protected reads.

## Authority boundary

Allowed now: local source-evidence diagnosis and, after root cause is known, the minimum source-only correction needed to retest provenance.

Forbidden: stock/SPY/options outcomes, protected candidate/return reads, provider mutations, broker/account reads or writes, orders, PAPER submits, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

Phase33 signal-to-trade remains blocked.
