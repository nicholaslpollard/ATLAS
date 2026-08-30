# Phase32 Independent Predictor/Source Acceptance

**Status:** ACTIVE — full-history source/predictor acquisition passed on the target machine; this independent local-only acceptance gate must pass before any development return may be opened.

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

The acquisition also retained 37 contradictory LONG/SHORT instrument sessions and excluded those groups under the frozen `EXCLUDE_ALL` rule.

## Independent acceptance contract

`phase32-predictor-independent-acceptance-v1-local-immutable-source-only`

Implementation:

- `packages/backtesting/phase32_predictor_acceptance.py`;
- `scripts/run_phase32_predictor_independent_acceptance.py`;
- `scripts/validate_phase32_predictor_independent_acceptance.py`;
- `tests/unit/test_phase32_predictor_independent_acceptance.py`.

This gate has **no provider or network client dependency**. It reads the completed local source caches and immutable source/predictor artifacts only.

## Mandatory independent checks

The gate independently revalidates:

1. the frozen Phase32 policy fingerprint, acquisition contract, identity-v4 contract, filing-entity key rule, source range, and accepted taxonomy hash;
2. the target-machine filing-entity and predictor SHA-256 values above;
3. zero market-outcome, protected-return, provider-write, broker, order, PAPER, LIVE, and automation counters;
4. every monthly original-8-K index and semantic disclosure cache against the reported source windows and row counts;
5. exact frozen taxonomy assignment without introducing new semantic categories or changing candidate direction;
6. accession-wide filing-date consistency and the date-bearing `accession|issuer CIK|filing date` filing-entity key;
7. accession-wide disclosure co-filer provenance while keeping candidate assignment issuer-specific;
8. original-8-K index issuer membership, filing date, form, issuer/co-filer row counts, and ticker-source isolation;
9. cached official SEC accession + issuer CIK + filing date + original `8-K` + acceptance-time lineage, including recomputation of the SEC source-record hash;
10. Massive Text multiplicity from the local raw cache: one or more rows are allowed only when all non-ticker fields are identical, every ticker variant is retained, and both aggregate-row-set and shared-non-ticker hashes match;
11. the provider-native ticker union from issuer disclosure, issuer index, and Massive Text evidence;
12. point-in-time identity-v4 resolution independently from the cached historical reference wrappers at both decision and exit sessions, including exact filing-CIK equality, strong/medium-only identity, interval continuity, uniqueness, and fail-closed ambiguity;
13. first XNYS regular-session open strictly after SEC acceptance time and the five-session exit chronology;
14. development / outer-embargo / protected-predictor-only / outside-window source stages;
15. every source/identity exclusion reason;
16. deterministic candidate/instrument/session aggregation;
17. contradictory LONG/SHORT instrument-session exclusion;
18. byte-for-byte regeneration of the complete predictor JSONL from independently verified filing-entity evidence;
19. all reported predictor/source counts and hashes.

The gate writes only one derived acceptance artifact:

`data/derived/strategy_evaluation/phase32/predictor_v1/phase32_predictor_independent_acceptance.json`

Its fingerprint is not known in advance. It is computed only after the target machine independently reproduces and accepts the completed source/predictor evidence.

## Authority boundary

A PASS here permits **development-return evaluation only** under the already-frozen Phase32 scientific policy.

It does **not** establish alpha, does not open protected returns, does not grant Phase33 signal-to-trade authority, and does not permit provider mutation, broker/account reads, orders, PAPER, LIVE, automation writes, or automatic broker failover.

If this gate fails for any reason, Phase32 progression stops and the source/lineage/identity defect must be diagnosed and corrected before development returns are opened.
