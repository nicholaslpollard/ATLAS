# Phase32 Independent Predictor/Source Acceptance

**Status:** ACCEPTED PASS on the target machine before any Phase32 market-outcome read.

Independent acceptance fingerprint:

`531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`

## Accepted input under audit

Target-machine acquisition contract:

`phase32-predictor-source-acquisition-v1-resumable-no-market-outcomes`

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Target-machine acquisition PASS produced:

- original-8-K index rows: **345,800**;
- semantic disclosure rows: **387,770**;
- frozen-candidate source accessions: **36,277**;
- filing-entity records: **36,309**;
- multi-filer candidate accessions: **32**;
- eligible predictor rows: **19,792**;
- development predictor rows: **18,819**;
- protected-predictor-only rows: **973**;
- stock / SPY / options / protected return rows read: **0 / 0 / 0 / 0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE: **0 / 0 / 0 / 0 / 0 / 0**.

Target filing-entity evidence SHA-256:

`18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`

Target predictor SHA-256:

`c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`

Candidate predictor counts:

- `equity_issuance_short`: 9,302;
- `financial_integrity_adverse_short`: 1,153;
- `listing_distress_short`: 4,665;
- `share_repurchase_long`: 3,410;
- `solvency_distress_short`: 1,262.

The acquisition retained 37 contradictory LONG/SHORT instrument sessions and excluded those groups under the frozen `EXCLUDE_ALL` rule.

## Independent acceptance contract

`phase32-predictor-independent-acceptance-v1-local-immutable-source-only`

Implementation:

- `packages/backtesting/phase32_predictor_acceptance.py`;
- `scripts/run_phase32_predictor_independent_acceptance.py`;
- `scripts/validate_phase32_predictor_independent_acceptance.py`;
- `tests/unit/test_phase32_predictor_independent_acceptance.py`.

The gate has no provider/network client dependency. It reads completed local source caches and immutable source/predictor artifacts only.

## First target-machine audit stop — validator exact-byte defect

The first independent audit stopped on filing entity `0000003545-23-000037|0000003545|2023-12-14` with `SEC source-record hash mismatch`, before any market outcome was opened.

A read-only diagnostic proved the cached SEC record and filing-entity evidence were internally consistent:

- stored SEC source-record SHA-256: `27dff5440916338d8f7f18d9ddfd12f543c76b340d8122cc7c19e77a1b5a932e`;
- filing-entity SEC SHA-256: the same value;
- SHA-256 of the exact cached `source_record_json` string: the same value;
- the canonical SEC source record intentionally ends with exactly one LF (`\n`);
- stripping that LF produces a different SHA-256: `d8583708836dcd467867857342cb58f35c789464392fccde0369327a7aeb5ccb`.

Root cause: the independent audit passed `source_record_json` through generic `_nonblank()`, which strips surrounding whitespace and therefore removed the canonical trailing LF before hashing. The source cache, filing-entity evidence, acquisition hashes, scientific policy, and protected boundary were correct.

Correction: exact byte-level lineage now uses `_exact_nonblank_text()`, which verifies nonblank content without altering whitespace. A regression pins preservation of the canonical trailing LF. No source artifact was rewritten and no scientific rule changed.

## Accepted target-machine result

The corrected independent audit reprocessed all **36,309** filing entities and passed with:

- source rows: index **345,800**, disclosures **387,770**;
- candidate accessions **36,277**;
- filing entities **36,309**;
- multi-filer accessions **32**;
- eligible predictors **19,792**;
- development predictors **18,819**;
- protected-predictor-only rows **973**;
- independent network reads **0**;
- stock / SPY / options / protected return rows **0 / 0 / 0 / 0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE **0 / 0 / 0 / 0 / 0 / 0**;
- filing-entity SHA-256 exactly `18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31`;
- predictor SHA-256 exactly `c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9`;
- independent acceptance fingerprint exactly `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

The accepted artifact is:

`data/derived/strategy_evaluation/phase32/predictor_v1/phase32_predictor_independent_acceptance.json`

## Mandatory independent checks

The accepted gate independently revalidated the frozen policy/acquisition/identity contracts, exact source hashes, zero outcome/remote-activity counters, monthly source caches, taxonomy assignment, filing-entity and co-filer provenance, official SEC lineage, Massive Text multiplicity, provider ticker unions, identity-v4 resolution, acceptance-time chronology, source stages, exclusion reasons, deterministic event aggregation, contradictory LONG/SHORT exclusion, byte-for-byte predictor regeneration, and all reported counts/hashes.

## Authority boundary after PASS

This PASS permits **development-return evaluation only** under the already-frozen Phase32 scientific policy.

It does **not** establish alpha. Protected stock/SPY returns remain forbidden until development selection/internal validation freezes finalists and a separate blindness/lineage audit passes. Phase33 signal-to-trade authority remains false. Provider mutation, broker/account reads, orders, PAPER, LIVE, automation writes, and automatic broker failover remain forbidden.
