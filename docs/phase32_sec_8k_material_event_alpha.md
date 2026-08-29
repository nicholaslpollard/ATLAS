# Phase 32 — SEC 8-K Material Corporate-Event Alpha

**Status:** ACTIVE — core source V2, semantic source V2, and source/taxonomy census are accepted PASS. The corrected complete scientific policy is frozen under fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`. Full-history predictor/source acquisition is active; Phase32 market outcomes remain unread and Phase33 remains blocked.

**Source foundation:** Phase31 PR #35 merge `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4` (`ACCEPTED_NEGATIVE`) with zero protected-return reads.

## Accepted core source progression

V1 SEC archive/header presentation paths remain retained as failed source evidence in `docs/phase32_sec_edgar_access_incident.md`.

Accepted core V2 contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Fingerprint:

`978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`

Target-machine core V2 result: **PASS** with 6,048 original-8-K index rows, 5,272 ticker-linked rows, 48 official SEC records, 94 SEC item codes, zero SEC filing-date mismatches, and **zero market outcomes** read.

Accepted source architecture remains Massive original-8-K discovery through `/stocks/filings/vX/index` plus official `data.sec.gov/submissions` metadata. Filing identity is exact accession + CIK + filing date + official SEC reconciliation. Public availability remains `FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME`.

## Semantic source progression

Rejected semantic V1 fingerprint:

`ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82`

V1 remains immutable `NOT ACCEPTED`. Its exact ticker equality and exact `supporting_text`-inside-`items_text` assumptions were diagnosed as invalid provider-scope invariants.

Accepted semantic V2 fingerprint:

`eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`

Semantic V2 target-machine result: **PASS** with taxonomy version 1.0 / 119 rows, 7,468 disclosure rows across five retained probe windows, complete exact original-8-K accession overlap, 30 Massive Text samples, 30 official SEC reconciliations, and zero target/protected outcome reads.

Ticker fields remain mapping metadata only. Nonblank taxonomy-linked `supporting_text` is required; `items_text` lexical comparison remains diagnostic only.

## Source/taxonomy census — ACCEPTED PASS

Contract:

`phase32-semantic-v2-source-census-v1-no-market-outcomes`

Target-machine PASS:

- taxonomy rows: 119;
- observed taxonomy rows: 112;
- disclosure rows: 7,468;
- unique accessions: 4,427;
- unique CIKs: 3,097;
- mapped/unmapped ticker rows: 6,231 / 1,237;
- target/protected outcome rows read: 0 / 0.

The census was source feasibility only. It did not inspect returns or establish alpha.

## Frozen scientific contract

Policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

The earlier proposed `0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88` fingerprint was superseded before acceptance and before any market-outcome read because its medium-identity prose omitted the accepted exact ticker component. The correction changed no hypothesis, outcome, cost, threshold, chronology, multiplicity rule, or protected evidence.

Exactly **five hypotheses** are frozen before performance:

1. `equity_issuance_short` — public offering, private placement, PIPE — SHORT;
2. `share_repurchase_long` — share repurchase program — LONG;
3. `financial_integrity_adverse_short` — accounting error correction, audit-opinion withdrawal, restatement, internal-control weakness — SHORT;
4. `listing_distress_short` — listing deficiency notice or delisting determination — SHORT;
5. `solvency_distress_short` — frozen debt-distress and bankruptcy/going-concern tags — SHORT.

Semantic families without a source-encoded universal sign—earnings/guidance, clinical/regulatory decisions, M&A without issuer-role direction, executive changes, general litigation, investor presentations, restructurings, routine financing, dividends, listing recovery/transfers, and bankruptcy emergence—are excluded from this Phase32 family.

Frozen execution/statistical contract:

- decision session = first XNYS session whose regular open timestamp is strictly after official SEC `acceptanceDateTime`;
- entry = decision-session open;
- exit = close 5 XNYS sessions later;
- SPY-relative directional return is primary; economically positive unhedged return is also mandatory;
- cost grid 0/5/10/25/50 bps, primary 10 bps, mandatory stress 25 bps;
- PIT identity is bound to `instrument-identity-v4-no-issuer-level-medium-collapse`;
- accepted identity quality is strong or medium only: strong = Composite FIGI / Share Class FIGI; medium = CIK + exact provider-native ticker + primary exchange + security type;
- exactly one CIK-matching `instrument_id` is required; ticker+snapshot fallback, alias backfill, and current-universe backprojection are forbidden;
- same candidate/instrument/session events aggregate with full accession/category lineage;
- same-direction cross-candidate overlap is retained; any LONG/SHORT contradiction on the same instrument/session excludes that instrument/session from all candidates;
- development last signal `2026-05-04`; 5-session outer embargo `2026-05-05..2026-05-11`; protected starts `2026-05-12`; last eligible protected signal `2026-08-04`; protected outcome end `2026-08-11`;
- chronological 75% selection region, 5-session internal purge, then internal validation;
- 6 selection folds / 3 internal / 3 protected; 5-session block bootstrap; 2,000 replicates;
- selection/internal/protected sample gates: 500/150/50 event rows, 200/60/20 signal sessions, 200/60/20 unique instruments;
- global `HOLM_BONFERRONI_GLOBAL_5`, family-wise alpha 0.05;
- at most one selection winner and one finalist per direction; **no runner-up substitution**;
- protected returns are finalist-only after an independent blindness/lineage audit.

Full normative contract: `docs/phase32_scientific_contract.md` and `packages/backtesting/phase32_policy.py`.

## Exact current action — full-history source/predictor acquisition

The next Phase32 task is **full-history** source/predictor acquisition for `2021-08-16..2026-08-11` under the frozen fingerprint.

It must acquire and reconcile:

1. original Massive 8-K discovery;
2. accepted semantic disclosure/taxonomy evidence;
3. official SEC `acceptanceDateTime` metadata;
4. exact accession/CIK provenance;
5. point-in-time instrument mapping under the accepted identity-v4 strong/medium uniqueness rule;
6. immutable lineage and source hashes.

### Joint/multi-filer index correction before outcomes

The target-machine acquisition stopped at accession `0000034903-25-000028` before any market-outcome read. The initial implementation required every Massive index row under one accession to have the semantic disclosure CIK. Official SEC evidence shows that accession is a valid joint 8-K containing Federal Realty Investment Trust (`CIK 0000034903`) and Federal Realty OP LP (`CIK 0001901876`), so accession multiplicity by filing entity is legitimate source provenance rather than corruption.

The corrected index-side source-reconciliation rule is:

- exact accession remains the filing-level join key;
- the semantic disclosure CIK remains the issuer identity being evaluated;
- every index row for that accession must retain the same filing date and original `8-K` form;
- at least one index row must match the disclosure issuer CIK;
- other CIKs are retained explicitly as co-filer provenance;
- only index rows whose CIK equals the disclosure issuer CIK may contribute index ticker mappings to PIT instrument resolution;
- a missing issuer-CIK match remains a hard fail-closed source defect.

Regression coverage verifies both the valid joint-filer index case and the missing-issuer failure case.

### Multi-filer disclosure partition correction before outcomes

A later target-machine rerun at head `96bacd387bca81cad0cdb014db759a5be67fb9c5` stopped at accession `0001057877-22-000019` with `candidate disclosure accession has inconsistent CIK/date`. This exposed the same legitimate multi-registrant filing structure on the semantic-disclosure side: the acquisition still grouped all frozen-candidate disclosure rows by accession alone even though the accepted semantic identity rule is exact accession + issuer CIK + filing date + official SEC reconciliation.

The corrected full-history filing-entity source key is now explicitly pinned as:

`EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE`

The production acquisition now:

- requires exactly one filing date across all frozen-candidate disclosure rows sharing an accession; a date conflict remains a hard failure;
- partitions those disclosure rows by zero-padded issuer CIK and processes each `(accession, issuer CIK)` filing entity independently;
- reconciles SEC metadata, Massive Text evidence, and original-8-K index membership independently for each filing entity;
- requires an issuer-CIK-matching index row and exact issuer-CIK Massive Text row for each filing entity;
- allows only that filing entity's disclosure rows, issuer-matching index rows, and issuer-matching Text row to contribute ticker mappings;
- preserves other disclosure/index CIKs as co-filer provenance instead of allowing them to contaminate issuer identity;
- writes source evidence as `candidate_filing_entity_records.jsonl`, distinguishing unique source accessions from filing-entity records and reporting source-stage counts at the filing-entity level.

Regression coverage now includes both a valid accession containing multiple disclosure CIKs and a negative same-accession conflicting-date case. The production runner is also pinned to the new filing-entity report schema so a successful acquisition cannot fail while rendering stale accession-only summary fields.

Neither multi-filer correction changes the frozen policy fingerprint, hypotheses, directions, chronology, costs, outcomes, thresholds, multiplicity controls, identity-v4 rules, or protected-evidence rules. **No development or protected market outcome has been read.** Existing monthly source caches remain reusable.

This acquisition must read **zero stock/SPY/options outcomes**. No development return may be opened until the full-history predictor/source gate passes without changing the frozen policy.

## Authority boundary

Allowed now: accepted immutable source evidence, frozen-policy validators/tests, full-history source/predictor acquisition, PIT instrument resolution, and documentation.

Forbidden: development/protected stock/SPY/options outcomes before the predictor/source gate, protected returns before finalists, provider mutations, broker/account reads or writes, orders, PAPER submissions, LIVE writes, frontend trading authority, automation writes, and automatic broker failover.

A source or policy PASS does not establish alpha. **Phase33 remains blocked** until Phase32 or another accepted alpha gate produces genuine historical `SUPPORTED` authority.
