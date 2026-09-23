# MarketData x Massive Disjoint EOD Validation V1 — 2026-09-23

## Status

**PREREGISTERED / WORKSTATION EVIDENCE PENDING**

This package converts the completed MarketData x Massive calibration into a disjoint,
binding validation gate. No validation-anchor provider data was inspected before the
sample and thresholds below were frozen.

## Calibration evidence

Accepted calibration run:

- run id: `20260923T205206Z`;
- evidence fingerprint:
  `b10d6d8eb2f3bfcb9fa9dad5623d1eb56297bec5222922b2b8f2302fe5324f3a`;
- status: `DIAGNOSTIC_COMPLETE`;
- exact-contract roots: SPY, MSFT, NVDA, QQQ;
- total overlapping sessions: 31;
- exact MarketData-last / Massive-close match rate: 77.419355%;
- aggregate median absolute last-close difference: $0.00;
- maximum observed absolute last-close difference: $0.82;
- MarketData last inside Massive daily low/high: 100%;
- aggregate median relative volume difference: 0.065284%;
- maximum observed relative volume difference: 14.213836%;
- no terminal error.

Contract-level exact-match rates ranged from 50% to 100%. This is why exact
last-close equality is retained as descriptive evidence rather than made a binding
criterion. The stronger semantic invariant observed during calibration was that every
MarketData historical last remained inside Massive's independently observed daily
trade range.

## Frozen disjoint validation sample

The validation sample uses no calibration root and no calibration anchor date:

| Root | Historical date |
| --- | --- |
| IWM | 2026-02-02 |
| AMZN | 2026-04-01 |
| META | 2026-06-01 |
| DIA | 2026-08-03 |

For each anchor ATLAS will:

1. request a MarketData historical EOD chain at approximately 30 DTE with
   `strikeLimit=8`;
2. choose one deterministic nearest-ATM call **for source-validation plumbing only**;
3. request ten calendar days of MarketData historical EOD quote rows for that exact
   OCC contract;
4. request the same exact contract and date range from Massive unadjusted 1Day
   aggregates; and
5. compare overlapping sessions.

The contract choice is not a simulator contract-selection rule and has no strategy
authority.

## Frozen binding thresholds

Each of all four anchors must satisfy every condition:

- at least 5 MarketData quote rows;
- at least 5 overlapping MarketData/Massive sessions;
- overlap sessions / MarketData quote rows = **100%**;
- MarketData historical last inside Massive daily low/high = **100%**;
- median relative MarketData-last / Massive-close difference <= **5%**;
- median relative MarketData-volume / Massive-volume difference <= **15%**.

Across all validation sessions:

- aggregate median relative last-close difference <= **2%**;
- aggregate median relative volume difference <= **10%**.

The exact last-close match rate is descriptive only and has no pass threshold.

### Threshold rationale

The calibration sample had 100% session overlap, 100% range containment, zero
aggregate median absolute last-close difference, and a maximum contract-level median
volume difference of approximately 5.31%. The validation limits deliberately allow
more dispersion than calibration so they test semantic compatibility without simply
reproducing the calibration observations:

- 5% contract-level price median;
- 2% aggregate price median;
- 15% contract-level volume median;
- 10% aggregate volume median.

The 100% overlap and range-containment requirements remain strict because a
MarketData EOD row that cannot be aligned to the same Massive session, or whose
reported last falls outside the independent daily trade range, would be a direct
semantic conflict for this limited use case.

## If the gate passes

A pass may establish only:

**MarketData historical EOD last/volume semantics validated against Massive daily
trade aggregates for candidate-first research use.**

It still does not establish:

- historical bid/ask validation;
- intraday option prices;
- option open prices;
- execution/slippage prices;
- a simulator entry/exit price policy;
- PIT contract selection;
- historical option P&L authority;
- strategy evidence;
- PAPER/LIVE authority;
- broker/order authority; or
- promotion/confluence authority.

Massive Basic does not independently validate historical bid/ask, so that remains a
separate source gate.

## If the gate fails

The frozen thresholds are not widened after observing validation outcomes. Any
failure is preserved as evidence. A new hypothesis would require a separately
versioned contract and a new disjoint sample.

## Expected provider cost

The validation should make:

- 8 MarketData reads: four chains + four selected-contract quote series;
- 4 Massive reads: one exact-contract daily aggregate series per anchor;
- 0 provider writes.

Under the currently observed Starter Trial accounting this should consume only a
small fraction of the remaining daily MarketData credits. Actual provider credit
headers are recorded in the report.

## Authority

Provider-source validation only. Strategy Evidence Register remains unchanged.
