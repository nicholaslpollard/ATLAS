# MarketData x Massive DIA Aggregate-Surface Diagnostic V1 — 2026-09-23

## Status

**PREREGISTERED / WORKSTATION EVIDENCE PENDING**

Contract:

`atlas-marketdata-massive-dia-aggregate-surface-diagnostic-v1`

This package follows the entitlement-blocked raw-trade diagnostic. It is a new
diagnostic and does not alter the frozen failed disjoint validation or the frozen
raw-trade diagnostic.

## Triggering evidence

The raw-trade diagnostic stopped under:

- run id: `20260923T222933Z`;
- evidence fingerprint:
  `48d58cecf4d084f241f8b6b008454427389be609c18d42ffcdcb318a12be4e6a`;
- status: `DIAGNOSTIC_INCOMPLETE`;
- condition metadata: 33 rows;
- first raw-trade date: 2026-08-06;
- terminal result: HTTP 403.

Current Massive documentation identifies that 403 as consistent with plan
entitlement: historical option trades are not included in Options Basic or Starter,
while custom option aggregate bars are included in Options Basic with end-of-day
recency and two years of history.

## Frozen hypothesis

If the missing daily bars are ordinary consequences of Massive's qualifying-trade
aggregate semantics, the same dates should also lack one-minute aggregate bars while
the dates that have daily bars should produce one-minute aggregate rows.

This is only an aggregate-surface consistency hypothesis. It does **not** prove
whether raw trades existed on a missing date and does not apply trade-condition
eligibility rules.

## Exact source evidence

The diagnostic reuses and verifies the accepted failed-validation evidence for:

- contract: `DIA260904C00531000`;
- window: 2026-08-03..2026-08-13;
- 9 MarketData EOD rows;
- 4 Massive daily aggregate rows;
- daily-bar dates: 2026-08-03, 2026-08-04, 2026-08-05 and 2026-08-11;
- missing daily-bar dates: 2026-08-06, 2026-08-07, 2026-08-10, 2026-08-12 and
  2026-08-13.

The failed validation remains `VALIDATION_FAILED` and immutable.

## Frozen procedure

ATLAS makes:

- **0 MarketData calls**;
- exactly **9 Massive reads**;
- one unadjusted 1-minute custom-aggregate request for each of the nine DIA dates;
- at most 50,000 base aggregates per date;
- 0 provider writes.

The existing Massive 5-requests/minute pacing remains authoritative.

For every date ATLAS preserves:

- whether the original Massive daily bar exists;
- MarketData EOD last, volume, bid and ask from the accepted raw evidence;
- original Massive daily volume when available;
- one-minute aggregate row count;
- summed one-minute aggregate volume;
- raw response and SHA-256 receipt;
- deterministic disposition.

Possible dispositions:

- `DAILY_AND_MINUTE_AGGREGATES_PRESENT`;
- `DAILY_AND_MINUTE_AGGREGATES_ABSENT`;
- `DAILY_PRESENT_MINUTE_ABSENT`;
- `DAILY_ABSENT_MINUTE_PRESENT`.

The aggregate surfaces are classified as consistent only when every daily-present
control has at least one minute bar and every daily-missing target date has no minute
bars.

## Interpretation boundary

`AGGREGATE_SURFACES_CONSISTENT` would support only this statement: Massive's daily
presence/absence pattern is reproduced on its finer aggregate surface for the frozen
DIA window.

It would **not** establish:

- that no raw trades occurred;
- that raw trades were ineligible under OPRA condition rules;
- that MarketData's EOD last or volume is independently validated;
- that the failed disjoint V1 should be reinterpreted; or
- historical option execution/simulator authority.

`AGGREGATE_SURFACE_INCONSISTENCY` would instead require investigation of Massive
aggregate construction or endpoint semantics before any coverage-aware V2 is designed.

Any validation V2 remains a new preregistered experiment on a new disjoint sample.

## Authority

Diagnostic only. No historical-price, bid/ask, intraday, execution, simulator,
strategy, PAPER, LIVE, broker/order, promotion or confluence authority.
