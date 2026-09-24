# MarketData x Massive Activity-Aware Disjoint EOD Validation V2 — 2026-09-23

## Status

**PREREGISTERED / WORKSTATION EVIDENCE PENDING**

Contract:

`atlas-marketdata-massive-disjoint-validation-v2`

V2 is a new validation experiment. It does not rerun or reinterpret the frozen
failed V1.

## Evidence basis

V1 failed under run `20260923T211759Z` because DIA had 9 MarketData EOD rows but
only 4 Massive daily bars. IWM, AMZN and META passed all frozen V1 criteria, and the
four overlapping DIA sessions passed price, range and volume checks.

The raw-trade diagnostic then stopped with HTTP 403 because historical option trades
are outside the current Massive plan. The separately preregistered aggregate-surface
diagnostic completed under run `20260923T225713Z` / fingerprint
`dadc60d4eb1bf4f33d123cdd1b8b09d92222f8e53b4fdb3a9a28c48b1d5b1487`.

That diagnostic observed:

- four MarketData sessions with positive volume: 3, 6, 41 and 1;
- those exact four sessions had Massive daily bars;
- those exact four sessions had Massive one-minute bars;
- summed Massive one-minute volume exactly equaled MarketData volume on all four;
- five MarketData sessions with volume 0;
- those exact five sessions had no Massive daily bar and no Massive minute bar.

Massive documents that option aggregate bars are constructed from qualifying trades
and that no bar is produced for an interval with no eligible trades. V2 therefore
tests activity concordance rather than requiring a trade-derived bar for every
MarketData EOD row.

## Frozen disjoint sample

No root or date from the prior MarketData x Massive calibration or V1 validation is
reused.

| Anchor | Date |
| --- | --- |
| AAPL | 2026-01-05 |
| TSLA | 2026-02-17 |
| AMD | 2026-03-16 |
| JPM | 2026-05-18 |
| XLF | 2026-07-06 |
| TLT | 2026-08-17 |

Prior cross-provider roots excluded from V2:
SPY, MSFT, NVDA, QQQ, IWM, AMZN, META and DIA.

Prior cross-provider dates excluded from V2:
2026-03-02, 2026-05-01, 2026-07-01, 2026-09-01, 2026-02-02,
2026-04-01, 2026-06-01 and 2026-08-03.

The sample and thresholds are frozen before any V2 provider read.

## Provider procedure

For each of six anchors ATLAS performs:

1. one restricted MarketData historical chain request;
2. the unchanged deterministic V1 qualification contract selector;
3. one MarketData selected-contract quote series covering 10 calendar days;
4. one exact-contract Massive unadjusted 1Day aggregate request for the same window.

Expected reads:

- MarketData: 12 total, six chains plus six quote series;
- Massive: 6 total;
- provider writes: 0.

All raw responses receive SHA-256 receipts.

## Activity-aware coverage rule

For every MarketData EOD session:

- finite `volume > 0` requires a Massive daily aggregate bar;
- `volume == 0` requires the Massive daily aggregate bar to be absent;
- missing/invalid MarketData volume fails the activity rule;
- a Massive daily bar for a date that MarketData omitted also fails the activity rule.

Activity concordance must be 100% for every anchor.

A zero-volume MarketData row can still contain a `last` value. V2 does **not**
interpret or validate that zero-volume `last` as an independent traded price.
Price/range/volume comparisons use only positive-volume sessions.

## Binding preregistered thresholds

Every anchor must satisfy:

- at least 5 MarketData quote rows;
- at least 5 positive-volume MarketData sessions;
- 100% activity concordance;
- one positive-volume Massive comparison for every positive-volume MarketData session;
- 100% MarketData-last containment inside Massive daily low/high on positive-volume
  sessions;
- median relative MarketData-last / Massive-close difference <=5%;
- median relative volume difference <=15%.

Across the complete six-anchor sample:

- all six anchors must pass;
- at least 30 positive-volume comparison sessions must exist;
- at least one zero-volume MarketData session must exist, so the new sparse-case rule
  is actually exercised;
- aggregate median relative price difference <=2%;
- aggregate median relative volume difference <=10%.

Exact MarketData-last / Massive-close equality remains descriptive only.

If the complete sample contains zero sparse sessions, V2 does not pass merely on
liquid cases; the sparse-case support requirement fails.

## Pass meaning

A V2 pass may validate only:

**MarketData historical EOD `last` and volume semantics on sessions where MarketData
reports positive volume, together with activity concordance between MarketData
positive/zero volume and Massive aggregate presence/absence for this disjoint sample.**

A pass does not validate MarketData `last` on zero-volume sessions.

Still outside authority:

- historical bid/ask;
- historical option open/intraday path;
- execution or slippage;
- simulator entry/exit pricing;
- PIT contract selection;
- option P&L simulation;
- strategy evidence;
- PAPER/LIVE;
- broker/order actions;
- promotion/confluence.

## Fail-closed rules

- thresholds are not changed after the first V2 provider read;
- anchors are not replaced after result inspection;
- V2 is not rerun to select a more favorable result;
- malformed/duplicate dates fail closed;
- positive-volume MarketData without a Massive bar fails;
- zero-volume MarketData with a Massive bar fails;
- extra Massive dates absent from MarketData fail;
- insufficient positive-volume support fails;
- absence of any sparse-case session in the complete sample fails the V2 sparse-case
  support requirement.

The original V1 remains `VALIDATION_FAILED` regardless of V2 outcome.
