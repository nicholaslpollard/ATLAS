# Pre-Phase33 Alpha Gate — SEC XBRL Fundamental Quality / Accrual Mechanism

**Status: FEASIBILITY_PASS accepted; source-only PIT chronology/identity audit is now OPEN. No alpha hypothesis is frozen, no market outcome has been read, and no trading authority is granted.**

## Purpose

ATLAS still has zero historically `SUPPORTED` modern alpha after valid negative Phases26–32, so Phase33 remains blocked. This gate tests a materially different information mechanism before any governed performance work: point-in-time standardized quarterly fundamentals from original SEC 10-Q/10-K filings.

The intended economic family is **fundamental profitability / cash-vs-accrual quality / fundamental change**, not another price-pattern, cross-sectional-return, lead-lag, relative-value, news-arrival, insider-transaction, or 8-K event-taxonomy variant.

External academic findings on gross profitability and accrual/cash-flow persistence motivate the mechanism only. They are not ATLAS performance evidence and do not authorize a candidate. ATLAS must independently establish source quality, point-in-time chronology, multiplicity treatment, robustness, costs, and protected evidence before any support can be earned.

## Authoritative source

Official SEC `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` is the authoritative standardized-fact route.

The implementation extends the already accepted `SECEDGARClient` network seam rather than adding a second SEC HTTP authority. Therefore the accepted HTTPS-only `data.sec.gov` host restriction, fair-access identity, request pacing, retry handling, compressed-response decoding, bounded response size, and caching remain in force.

The accepted source census used no Massive, broker, order, AI, PAPER, LIVE, or automation authority. The next source-only PIT audit additionally authorizes Massive reference **reads only** for exact CIK/date security identity; it still authorizes zero market outcomes and zero mutations.

## Source-only issuer inventory

The deterministic census seed is the accepted Phase32 predictor source inventory only because it already contains a large, PIT-audited set of issuer CIKs available on the target machine.

This reuse grants **no Phase32 scientific lineage** to the new mechanism:

- Phase32 candidate IDs, directions, 8-K item categories, development performance, finalist selection, and protected plan are not used.
- Only unique zero-padded `issuer_cik` values are extracted.
- The source file hash is recorded.
- Exactly 200 CIKs are chosen by ascending `SHA256(zero_padded_cik)` so the sample is deterministic and outcome-free.

## Frozen feasibility contract — ACCEPTED PASS

Contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Source Phase32 merge:

`69f8aa81289934b71f2652482c747391917c15a3`

Mechanism label:

`PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`

Source fact window: `2016-01-01..2026-08-11`.

Only standardized `us-gaap` facts attached to original `10-Q` or `10-K` records with a valid accession, period end, and filed date inside that window are counted.

Concept groups examined:

- assets: `Assets`;
- net income: `NetIncomeLoss`;
- operating cash flow: `NetCashProvidedByUsedInOperatingActivities`;
- revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, or `SalesRevenueNet`;
- gross profit: `GrossProfit`;
- cost of revenue: `CostOfRevenue` or `CostOfGoodsAndServicesSold`.

A concept group is history-ready when at least 8 distinct reported period ends are present in the bounded source window.

An issuer is **accrual-history-ready** when assets, net income, and operating cash flow are each history-ready.

An issuer is **profitability-history-ready** when assets and revenue are history-ready and either gross profit or cost of revenue is history-ready.

The frozen source-only feasibility gates were:

- deterministic sample = exactly 200 issuers;
- successful Company Facts documents >= 160;
- accrual-history-ready issuers >= 100;
- profitability-history-ready issuers >= 80.

### Accepted target-machine result

The target-machine runner passed on exact head:

`5a8c15f95417390d0d64ff240977adfb38a20c45`

Result: **`FEASIBILITY_PASS`**.

Accepted evidence:

- source inventory unique CIKs: **4,400**;
- sample size: **200**;
- successful Company Facts documents: **200**;
- failed Company Facts documents: **0**;
- accrual-history-ready issuers: **170**;
- profitability-history-ready issuers: **92**;
- group history-ready counts: assets **174**, cost of revenue **97**, gross profit **78**, net income **180**, operating cash flow **180**, revenue **136**;
- all four frozen feasibility gates: **PASS**;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider reads/writes: **200 / 0**;
- broker reads/writes, orders, PAPER, LIVE, automation: **0**.

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

The source census is therefore accepted as sufficient to justify the next source/chronology gate. It does **not** establish predictive value.

## Current gate — PIT source / chronology / identity audit

The next audit is frozen before any additional live source results under fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

It independently audits exact original 10-Q/10-K accession identity, official SEC `acceptanceDateTime`, first-XNYS-open chronology, accession-versioned fact/restatement handling, same-accession contradiction fail-closed behavior, and exact CIK/date Massive issuer-to-instrument mapping.

The audit uses exactly 40 deterministic feasibility-ready issuers and up to 5 evenly spaced original accessions per issuer. Frozen minimums are 36 successful Company Facts documents, 180 selected original filings, 170 SEC metadata reconciliations, 170 reconstructed acceptance-time decision sessions, 120 unambiguous PIT instrument mappings, 30 issuers with at least 3 unambiguous mappings, and zero same-accession semantic-context conflicts.

See `docs/alpha_gate_sec_xbrl_pit_audit.md`.

## Explicitly forbidden before scientific freeze

- stock, SPY, option, or other market returns;
- target outcomes or protected returns;
- ranking issuers or candidate ideas by performance;
- freezing alpha hypotheses after observing performance;
- changing the Phase32 holdout state;
- provider writes;
- broker reads/writes;
- orders, PAPER, LIVE, browser execution, scheduler execution, or automatic broker failover;
- use of Phase32 event labels/performance as predictors or selection evidence.

The master protected outcome window `2026-05-12..2026-08-11` therefore remains unconsumed throughout the source-only feasibility and PIT-audit work.

## Acceptance semantics

The accepted `FEASIBILITY_PASS` authorized only the current independent PIT source/chronology/identity audit.

An `AUDIT_PASS` at the next gate will authorize only the scientific freeze work package: a finite hypothesis family, outcome definitions, costs, chronology, dependence, multiplicity, robustness, sample/concentration gates, winner/finalist rules, and protected-evidence policy must all be frozen **before** any governed market outcome is opened.

An `AUDIT_FAIL` is also legitimate evidence. ATLAS must diagnose the source/chronology/identity limitation rather than loosen frozen thresholds, guess through ambiguous securities, or silently substitute a different dataset.

## Target-machine runners

Accepted feasibility runner:

`scripts/run_alpha_gate_xbrl_feasibility.py`

Current PIT audit runner:

`scripts/run_alpha_gate_xbrl_pit_audit.py`
