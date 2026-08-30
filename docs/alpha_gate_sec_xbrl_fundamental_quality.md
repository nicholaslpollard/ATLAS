# Pre-Phase33 Alpha Gate — SEC XBRL Fundamental Quality / Accrual Feasibility

**Status: OPEN — source-only feasibility. No alpha hypothesis is frozen, no market outcome has been read, and no trading authority is granted.**

## Purpose

ATLAS still has zero historically `SUPPORTED` modern alpha after valid negative Phases26–32, so Phase33 remains blocked. This gate tests a materially different information mechanism before any governed performance work: point-in-time standardized quarterly fundamentals from original SEC 10-Q/10-K filings.

The intended economic family is **fundamental profitability / cash-vs-accrual quality / fundamental change**, not another price-pattern, cross-sectional-return, lead-lag, relative-value, news-arrival, insider-transaction, or 8-K event-taxonomy variant.

External academic findings on gross profitability and accrual/cash-flow persistence motivate the mechanism only. They are not ATLAS performance evidence and do not authorize a candidate. ATLAS must independently establish source quality, point-in-time chronology, multiplicity treatment, robustness, costs, and protected evidence before any support can be earned.

## Authoritative source

Official SEC `data.sec.gov/api/xbrl/companyfacts/CIK##########.json` is the only provider route authorized in this feasibility gate.

The implementation extends the already accepted `SECEDGARClient` network seam rather than adding a second SEC HTTP authority. Therefore the accepted HTTPS-only `data.sec.gov` host restriction, fair-access identity, request pacing, retry handling, compressed-response decoding, bounded response size, and in-process caching remain in force. The XBRL client additionally restricts requests to one exact Company Facts CIK JSON path.

No Massive, broker, order, AI, PAPER, LIVE, or automation authority is used by this feasibility census.

## Source-only issuer inventory

The deterministic census seed is the accepted Phase32 predictor source inventory only because it already contains a large, PIT-audited set of issuer CIKs available on the target machine.

This reuse grants **no Phase32 scientific lineage** to the new mechanism:

- Phase32 candidate IDs, directions, 8-K item categories, development performance, finalist selection, and protected plan are not used.
- Only unique zero-padded `issuer_cik` values are extracted.
- The source file hash is recorded.
- Exactly 200 CIKs are chosen by ascending `SHA256(zero_padded_cik)` so the sample is deterministic and outcome-free.

## Frozen feasibility contract

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

The frozen source-only feasibility gates are:

- deterministic sample = exactly 200 issuers;
- successful Company Facts documents >= 160;
- accrual-history-ready issuers >= 100;
- profitability-history-ready issuers >= 80.

These are source-coverage gates only. They do not measure returns or claim predictive value.

## Explicitly forbidden in this gate

- stock, SPY, option, or other market returns;
- target outcomes or protected returns;
- ranking issuers or candidate ideas by performance;
- freezing alpha hypotheses after observing performance;
- changing the Phase32 holdout state;
- provider writes;
- broker reads/writes;
- orders, PAPER, LIVE, browser execution, scheduler execution, or automatic broker failover;
- use of Phase32 event labels/performance as predictors or selection evidence.

The master protected outcome window `2026-05-12..2026-08-11` therefore remains unconsumed during this feasibility step.

## Acceptance semantics

`FEASIBILITY_PASS` means only that the official standardized source appears sufficiently populated to justify the **next source/chronology gate**. It does not freeze a strategy, read outcomes, satisfy Phase33, or grant `SUPPORTED` authority.

`FEASIBILITY_FAIL` is also a legitimate scientific result. ATLAS must diagnose the source limitation rather than loosen the frozen coverage thresholds or silently substitute a different dataset.

If feasibility passes, the next work package must independently prove point-in-time filing/accession/acceptance chronology and deterministic original-filing fact reconstruction, including duplicate/restatement/amendment handling and issuer-to-instrument identity. Only after that source contract is accepted may ATLAS freeze a finite hypothesis family, outcomes, costs, multiplicity, dependence, robustness, sample gates, winner/finalist rules, and protected-evidence policy before governed performance is opened.

## Target-machine runner

`scripts/run_alpha_gate_xbrl_feasibility.py`

The runner is intentionally bounded to the frozen 200-issuer deterministic sample and emits progress while preserving zero-outcome authority.
