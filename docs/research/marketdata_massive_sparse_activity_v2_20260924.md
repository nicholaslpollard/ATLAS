# MarketData x Massive Sparse-Activity Confirmation V2 — 2026-09-24

## Status

**PREREGISTERED BEFORE EXECUTION / FIRST-RUN V2 PASSED 2026-09-25**

Contract:

`atlas-marketdata-massive-sparse-activity-confirmation-v2`

V2 is a new experiment. It does not rerun, repair or reinterpret the failed sparse
confirmation V1.

## Evidence basis

Sparse V1 run `20260924T033435Z` /
`d7ce4d184d175b6f60233f2a4470e8e4e67a27691ac8a45a082b805b9e3cce6d`
produced 105 observed sessions:

- 87 zero-volume sessions across all 12 anchors;
- 18 positive-volume sessions across 6 anchors;
- 100% activity concordance;
- zero mismatches of either direction;
- zero invalid-volume sessions;
- zero extra Massive dates.

V1 failed only because its positive-control minimum was 20, not 18. That threshold
remains unchanged and V1 remains failed.

The farthest-OTM design generated excellent sparse support but slightly insufficient
positive controls. V2 changes only the prospective contract-selection stress level,
not the hypothesis or pass thresholds.

## Frozen V2 sample

All roots and dates are new to prior MarketData x Massive cross-provider evidence.

| Order | Root | Anchor date |
| ---: | --- | --- |
| 1 | GLD | 2025-10-20 |
| 2 | SLV | 2025-11-17 |
| 3 | GDX | 2025-12-15 |
| 4 | USO | 2026-01-26 |
| 5 | XLE | 2026-02-23 |
| 6 | XLK | 2026-03-23 |
| 7 | XLY | 2026-04-20 |
| 8 | XLP | 2026-05-11 |
| 9 | XLU | 2026-06-22 |
| 10 | XLI | 2026-07-20 |
| 11 | XLV | 2026-08-10 |
| 12 | XLRE | 2026-09-14 |

No anchor may be replaced after observation.

## Frozen selector

For every anchor, ATLAS requests a historical call chain with:

- DTE target: 30;
- strike limit: 20;
- side: call.

Eligible contracts must be calls with finite positive strike and underlying price
and must be out of the money.

The deterministic selection order is:

1. rank eligible calls by strike / underlying-price ratio descending;
2. break equal-ratio ties by OCC option symbol ascending;
3. choose the **third-farthest OTM** contract.

If fewer than three eligible OTM calls exist, the experiment fails closed.

The selector does not inspect quote-series volume, quote-series future path, Massive
data, or any activity outcome.

## Provider procedure

For each of 12 anchors:

1. one MarketData historical chain read;
2. deterministic third-farthest-OTM selection;
3. one MarketData selected-contract quote series over 10 calendar days;
4. one exact-contract Massive unadjusted 1Day aggregate request for the same window.

Expected reads:

- MarketData: 24;
- Massive: 12;
- writes: 0.

All raw responses receive SHA-256 receipts.

## Session rule

Every MarketData session counts.

- MarketData `volume == 0` requires no Massive daily aggregate;
- MarketData `volume > 0` requires a Massive daily aggregate;
- invalid/negative MarketData volume fails;
- any extra Massive date absent from MarketData fails.

No price threshold is evaluated in this experiment. A zero-volume MarketData
`last` remains uninterpreted.

## Binding thresholds

V2 retains the exact V1 support and concordance requirements:

- exactly 12 completed anchors;
- at least 5 MarketData rows per anchor;
- at least 10 zero-volume sessions total;
- zero-volume sessions across at least 3 anchors;
- at least 20 positive-volume sessions total;
- positive-volume sessions across at least 3 anchors;
- activity concordance = 100%;
- zero zero-volume/Massive-present mismatches;
- zero positive-volume/Massive-missing mismatches;
- zero invalid-volume sessions;
- zero extra Massive dates.

These thresholds, roots, dates and selector are frozen before any V2 provider read.

## Pass meaning

A pass confirms the MarketData zero/positive-volume activity state against Massive
trade-derived daily aggregate presence/absence on this fresh mixed-activity sample.

A pass still does not validate:

- MarketData `last` on zero-volume sessions;
- positive-volume price semantics by itself;
- bid/ask;
- intraday option paths;
- execution/slippage;
- simulator option P&L;
- strategy/PAPER/LIVE/broker/order/promotion/confluence.

If V2 passes, a later synthesis package may combine the already-frozen
positive-volume price evidence from disjoint validation V2 with the independent
activity-confirmation evidence. Neither historical failed validation is relabeled as
a pass.

## Fail-closed rules

- no post-result selector change;
- no threshold reduction;
- no anchor replacement;
- no rerun to select a favorable result;
- every observed session counts;
- provider/malformed-data errors prevent a pass;
- sparse V1 and disjoint validations V1/V2 remain immutable failures regardless of
  this result.

## First-run workstation acceptance — 2026-09-25

The frozen V2 test returned `SPARSE_ACTIVITY_CONCORDANCE_CONFIRMED`,
run `20260925T184421Z` / fingerprint
`398ca760a7e05126e18008c6e7c09fc2f9d03e8a07b5a9a95e0282891d4c2d69`.
All 12 anchors produced 106 observations: 38 zero-volume over 8 anchors,
68 positive-volume over 11 anchors, and 106/106 concordance against independent
Massive aggregate absence/presence. Every frozen check passed; mismatches, invalid
volume, extra Massive dates, and terminal errors were all zero. Observed MarketData
credit consumption was 24, with 9,966 remaining in the last header. Preserve the
first-run result without alteration or reread.

Acceptance and full anchor counts:
`docs/research/marketdata_sparse_activity_v2_acceptance_20260925.md`.
Conservative joint interpretation and unchanged historical failed verdicts:
`docs/research/marketdata_eod_semantics_synthesis_v1_20260925.md`.
