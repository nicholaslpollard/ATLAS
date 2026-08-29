# Phase 32 — Semantic 8-K Source Qualification

**Status:** STOPPED FOR ROOT-CAUSE DIAGNOSIS. Semantic V1 is **NOT ACCEPTED**. No alpha hypothesis is frozen and no market outcome is authorized.

## Accepted prerequisite

Phase32 core source feasibility V2 remains accepted:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine V2 result: **PASS** with 6,048 original-8-K index rows, 48 reconciled official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and zero target/protected return reads.

## Semantic V1 — retained rejected evidence

Contract:

`phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes`

Fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

Target-machine execution reached the semantic source checks and returned **NOT ACCEPTED** because:

- `all_sampled_tickers_align` failed;
- `all_sampled_supporting_text_is_grounded` failed.

The run read **zero market outcomes**, zero protected candidates/returns, and created no provider/broker/order/PAPER/LIVE authority. Its evidence is retained for diagnosis and must not be reinterpreted as alpha evidence.

## Contract defect discovered after the failed run

Semantic V1 also hard-coded a provider-history claim of **January 2022** and a `2022-01-03` safe-history start. That claim was not established by the Massive endpoint documentation supplied during Phase32; those docs state **Plan History: Not applicable to this endpoint**.

Therefore the January-2022 boundary is **not accepted provenance** and may not be carried into a corrected semantic contract merely because V1 encoded it. Because V1 was source-only and read no returns, the source contract can be corrected without performance contamination.

The failed V1 remains preserved rather than deleted or rewritten.

## Current diagnostic target

Before changing ticker or text-grounding rules, ATLAS must identify the actual cause of the two failed checks from the immutable source evidence produced by V1.

Diagnostic:

`scripts/diagnose_phase32_semantic_failure.py`

The diagnostic performs no network calls and no market-outcome reads. It reports, for each failing sampled accession:

- disclosure ticker set;
- Massive index ticker set;
- Massive 8-K Text ticker;
- failed grounding records;
- normalized support/text lengths;
- token coverage;
- bounded source-text excerpts.

## Root-cause rule

Do not weaken ticker alignment or supporting-text grounding to obtain PASS. Determine whether the failure is caused by:

1. an ATLAS interpretation/validation bug;
2. a documented difference in provider field semantics;
3. provider source inconsistency; or
4. an ultimately infeasible semantic-source method.

Correct an ATLAS defect first when one exists. Only after the intended method is genuinely shown infeasible may a different source method be defined.

## Authority boundary

Still forbidden: stock/SPY/options outcomes, protected returns, hypothesis direction/horizon selection from returns, provider writes, broker/account reads or writes, orders, PAPER submits, LIVE writes, automation writes, and automatic broker failover.

Phase33 remains blocked.
